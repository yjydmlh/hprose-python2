############################################################
#                                                          #
#                          hprose                          #
#                                                          #
# Official WebSite: http://www.hprose.com/                 #
#                   http://www.hprose.net/                 #
#                   http://www.hprose.org/                 #
#                                                          #
############################################################

############################################################
#                                                          #
# hprose/server.py                                         #
#                                                          #
# hprose server for python 2.3+                            #
#                                                          #
# LastModified: Mar 12, 2014                               #
# Author: Ma Bingyao <andot@hprose.com>                    #
#                                                          #
############################################################

import types, traceback
from sys import modules, exc_info
from hprose.io import *
from hprose.common import *

def _getInstanceMethods(cls):
    v = vars(cls)
    return [name for name in v if isinstance(v[name], types.FunctionType)]

def _getClassMethods(cls):
    v = vars(cls)
    return [name for name in v if isinstance(v[name], classmethod)]

def _getStaticMethods(cls):
    v = vars(cls)
    return [name for name in v if isinstance(v[name], staticmethod)]

class HproseService(object):
    def __init__(self):
        self.__functions = {}
        self.__funcNames = {}
        self.__resultMode = {}
        self.__simpleMode = {}
        self.debug = False
        self.filter = HproseFilter()
        self.simple = False
        self.onBeforeInvoke = None
        self.onAfterInvoke = None
        self.onSendHeader = None
        self.onSendError = None

    def _responseEnd(self, ostream):
        data = self.filter.outputFilter(ostream.getvalue())
        ostream.close()
        return data

    def _fixArgs(self, args, function, context):
        if hasattr(function, 'func_code'):
            fc = function.func_code
            c = fc.co_argcount
            if (len(args) + 1 == c) and (c > 0) and (fc.co_varnames[c - 1] == 'context'):
                args.append(context)
        return args

    def _fireBeforeInvokeEvent(self, name, args, byref, context):
        if self.onBeforeInvoke != None:
            if hasattr(self.onBeforeInvoke, 'func_code'):
                argcount = self.onBeforeInvoke.func_code.co_argcount
                if argcount == 4:
                    self.onBeforeInvoke(name, args, byref, context)
                elif argcount == 3:
                    self.onBeforeInvoke(name, args, byref)
                elif argcount == 2:
                    self.onBeforeInvoke(name, args)
                elif argcount == 1:
                    self.onBeforeInvoke(name)
                elif argcount == 0:
                    self.onBeforeInvoke()
            else:
                self.onBeforeInvoke(name, args, byref, context)

    def _fireAfterInvokeEvent(self, name, args, byref, result, context):
        if self.onAfterInvoke != None:
            if hasattr(self.onAfterInvoke, 'func_code'):
                argcount = self.onAfterInvoke.func_code.co_argcount
                if argcount == 5:
                    self.onAfterInvoke(name, args, byref, result, context)
                elif argcount == 4:
                    self.onAfterInvoke(name, args, byref, result)
                elif argcount == 3:
                    self.onAfterInvoke(name, args, byref)
                elif argcount == 2:
                    self.onAfterInvoke(name, args)
                elif argcount == 1:
                    self.onAfterInvoke(name)
                elif argcount == 0:
                    self.onAfterInvoke()
            else:
                self.onAfterInvoke(name, args, byref, result, context)

    def _fireErrorEvent(self, e, context):
        if self.onSendError != None:
            if hasattr(self.onSendError, 'func_code'):
                argcount = self.onSendError.func_code.co_argcount
                if argcount == 2:
                    self.onSendError(e, context)
                elif argcount == 1:
                    self.onSendError(e)
                elif argcount == 0:
                    self.onSendError()
            else:
                self.onSendError(e, context)

    def _doError(self, e, context):
        self._fireErrorEvent(e, context)
        if self.debug:
            e = ''.join(traceback.format_exception(*exc_info()))
        ostream = StringIO()
        writer = HproseWriter(ostream, True)
        ostream.write(HproseTags.TagError)
        writer.writeString(str(e).encode('utf-8'))
        ostream.write(HproseTags.TagEnd)
        return self._responseEnd(ostream)

    def _doInvoke(self, istream, context):
        simpleReader = HproseReader(istream, True)
        tag = HproseTags.TagCall
        while tag == HproseTags.TagCall:
            name = simpleReader.readString()
            aliasname = name.lower()
            if isinstance(aliasname, str):
                aliasname = unicode(aliasname, 'utf-8')
            args = []
            byref = False
            tag = simpleReader.checkTags((HproseTags.TagList,
                                          HproseTags.TagEnd,
                                          HproseTags.TagCall))
            if tag == HproseTags.TagList:
                reader = HproseReader(istream)
                args = reader.readListWithoutTag()
                tag = reader.checkTags((HproseTags.TagTrue,
                                        HproseTags.TagEnd,
                                        HproseTags.TagCall))
                if (tag == HproseTags.TagTrue):
                    byref = True
                    tag = reader.checkTags((HproseTags.TagEnd,
                                            HproseTags.TagCall))
            self._fireBeforeInvokeEvent(name, args, byref, context)
            if aliasname in self.__functions:
                function = self.__functions[aliasname]
                resultMode = self.__resultMode[aliasname]
                simple = self.__simpleMode[aliasname]
                result = function(*self._fixArgs(args, function, context))
            elif u'*' in self.__functions:
                function = self.__functions[u'*']
                resultMode = self.__resultMode[u'*']
                simple = self.__simpleMode[u'*']
                result = function(name, args)
            else:
                raise HproseException, "Can't find this function %s()." % name
            self._fireAfterInvokeEvent(name, args, byref, result, context)
            ostream = StringIO()
            if resultMode == HproseResultMode.RawWithEndTag:
                return self.filter.outputFilter(result)
            if resultMode == HproseResultMode.Raw:
                ostream.write(result)
            else:
                ostream.write(HproseTags.TagResult)
                if resultMode == HproseResultMode.Serialized:
                    ostream.write(result)
                else:
                    if simple == None: simple = self.simple
                    writer = HproseWriter(ostream, simple)
                    writer.serialize(result)
                    if byref:
                        ostream.write(HproseTags.TagArgument)
                        writer.reset()
                        writer.writeList(args)
        ostream.write(HproseTags.TagEnd)
        return self._responseEnd(ostream)

    def _doFunctionList(self):
        ostream = StringIO()
        writer = HproseWriter(ostream, True)
        ostream.write(HproseTags.TagFunctions)
        writer.writeList(self.__funcNames.values())
        ostream.write(HproseTags.TagEnd)
        return self._responseEnd(ostream)

    def _handle(self, data, context):
        istream = None
        try:
            data = self.filter.inputFilter(data)
            if data == None or data == '' or data[len(data) - 1] != HproseTags.TagEnd:
                raise HproseException, "Wrong Request: \r\n%s" % data
            istream = StringIO(data)
            tag = istream.read(1)
            if tag == HproseTags.TagCall:
                return self._doInvoke(istream, context)
            elif tag == HproseTags.TagEnd:
                return self._doFunctionList()
            else:
                raise HproseException, "Wrong Request: \r\n%s" % data
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, e:
            return self._doError(e, context)

    def addMissingFunction(self, function, resultMode = HproseResultMode.Normal, simple = None):
        self.addFunction(function, u'*', resultMode, simple)

    def addFunction(self, function, alias = None, resultMode = HproseResultMode.Normal, simple = None):
        if isinstance(function, (str, unicode)):
            function = getattr(modules['__main__'], function, None)
        if not callable(function):
            raise HproseException, 'Argument function is not callable'
        if alias == None:
            alias = function.__name__
        if isinstance(alias, str):
            alias = unicode(alias, 'utf-8')
        if isinstance(alias, unicode):
            aliasname = alias.lower()
            self.__functions[aliasname] = function
            self.__funcNames[aliasname] = alias
            self.__resultMode[aliasname] = resultMode
            self.__simpleMode[aliasname] = simple
        else:
            raise HproseException, 'Argument alias is not a string'

    def addFunctions(self, functions, aliases = None, resultMode = HproseResultMode.Normal, simple = None):
        aliases_is_null = (aliases == None)
        if not isinstance(functions, (list, tuple)):
            raise HproseException, 'Argument functions is not a list or tuple'
        count = len(functions)
        if not aliases_is_null and count != len(aliases):
            raise HproseException, 'The count of functions is not matched with aliases'
        for i in xrange(count):
            function = functions[i]
            if aliases_is_null:
                self.addFunction(function, None, resultMode, simple)
            else:
                self.addFunction(function, aliases[i], resultMode, simple)

    def addMethod(self, methodname, belongto, alias = None, resultMode = HproseResultMode.Normal, simple = None):
        function = getattr(belongto, methodname, None)
        if alias == None:
            self.addFunction(function, methodname, resultMode, simple)
        else:
            self.addFunction(function, alias, resultMode, simple)

    def addMethods(self, methods, belongto, aliases = None, resultMode = HproseResultMode.Normal, simple = None):
        aliases_is_null = (aliases == None)
        if not isinstance(methods, (list, tuple)):
            raise HproseException, 'Argument methods is not a list or tuple'
        if isinstance(aliases, (str, unicode)):
            if isinstance(aliases, str):
                aliasPrefix = aliases
            else:
                aliasPrefix = aliases.encode('utf-8')
            aliases = [aliasPrefix + '_' + name for name in methods]
        count = len(methods)
        if not aliases_is_null and count != len(aliases):
            raise HproseException, 'The count of methods is not matched with aliases'
        for i in xrange(count):
            method = methods[i]
            function = getattr(belongto, method, None)
            if aliases_is_null:
                self.addFunction(function, method, resultMode, simple)
            else:
                self.addFunction(function, aliases[i], resultMode, simple)

    def addInstanceMethods(self, obj, cls = None, aliasPrefix = None, resultMode = HproseResultMode.Normal, simple = None):
        if cls == None: cls = obj.__class__
        self.addMethods(_getInstanceMethods(cls), obj, aliasPrefix, resultMode, simple)

    def addClassMethods(self, cls, execcls = None, aliasPrefix = None, resultMode = HproseResultMode.Normal, simple = None):
        if execcls == None: execcls = cls
        self.addMethods(_getClassMethods(cls), execcls, aliasPrefix, resultMode, simple)

    def addStaticMethods(self, cls, aliasPrefix = None, resultMode = HproseResultMode.Normal, simple = None):
        self.addMethods(_getStaticMethods(cls), cls, aliasPrefix, resultMode, simple)

    def add(self, *args):
        args_num = len(args)
        if args_num == 1:
            if isinstance(args[0], (tuple, list)):
                self.addFunctions(args[0])
            elif isinstance(args[0], (types.TypeType, types.ClassType)):
                self.addClassMethods(args[0])
                self.addStaticMethods(args[0])
            elif callable(args[0]):
                self.addFunction(args[0])
            else:
                self.addInstanceMethods(args[0])
        elif args_num == 2:
            if isinstance(args[0], (types.TypeType, types.ClassType)):
                if isinstance(args[1], (types.TypeType, types.ClassType)):
                    self.addClassMethods(args[0], args[1])
                else:
                    self.addClassMethods(args[0], args[0], args[1])
                    self.addStaticMethods(args[0], args[1])
            elif isinstance(args[0], (str, unicode)):
                if isinstance(args[1], (str, unicode)):
                    self.addFunction(args[0], args[1])
                else:
                    self.addMethod(args[0], args[1])
            elif isinstance(args[0], (tuple, list)):
                if isinstance(args[1], (tuple, list)):
                    self.addFunctions(args[0], args[1])
                else:
                    self.addMethods(args[0], args[1])
            elif callable(args[0]) and isinstance(args[1], (str, unicode)):
                self.addFunction(args[0], args[1])
            elif isinstance(args[1], (str, unicode)):
                self.addInstanceMethods(args[0], None, args[1])
            else:
                self.addInstanceMethods(args[0], args[1])
        elif args_num == 3:
            if isinstance(args[0], (str, unicode)) and isinstance(args[2], (str, unicode)):
                if args[1] == None:
                    self.addFunction(args[0], args[2])
                else:
                    self.addMethod(args[0], args[1], args[2])
            elif isinstance(args[0], (tuple, list)):
                if isinstance(args[2], (tuple, list)) and args[1] == None:
                    self.addFunctions(args[0], args[2])
                else:
                    self.addMethods(args[0], args[1], args[2])
            elif isinstance(args[1], (types.ClassType, types.TypeType)) and isinstance(args[2], (str, unicode)):
                if isinstance(args[0], (types.ClassType, types.TypeType)):
                    self.addClassMethods(args[0], args[1], args[2])
                else:
                    self.addInstanceMethods(args[0], args[1], args[2])
            elif callable(args[0]) and args[1] == None and isinstance(args[2], (str, unicode)):
                self.addFunction(args[0], args[2])
            else:
                raise HproseException, 'Wrong arguments'
        else:
            raise HproseException, 'Wrong arguments'
