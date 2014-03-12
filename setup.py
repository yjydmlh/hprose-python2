import sys, os.path
if sys.version_info < (2, 3):
    print >> sys.stderr, 'error: python 2.3 or higher is required, you are using %s' %'.'.join([str(i) for i in sys.version_info])

    sys.exit(1)

def main():
    import ez_setup
    ez_setup.use_setuptools()

    from setuptools import setup
    args = dict(
        name = 'hprose',
        version = '1.4.1',
        description = 'Hprose is a High Performance Remote Object Service Engine.',
        author = 'Ma Bingyao',
        url = 'http://www.hprose.com',
        platforms = 'any',
        packages = ('hprose', ),
        zip_safe = False )

    data_files = []
    os.path.walk('skel', skel_visit, data_files)
    if sys.version_info < (3, 0):args['install_requires'] = ['fpconst']


    args['data_files']  = data_files
    args['package_dir'] = {'hprose': os.path.join('src', 'hprose')}

    args['classifiers'] = [
        'Development Status :: 1 - Stable',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Topic :: Internet',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Object Brokering',
        'Topic :: Software Development :: Libraries :: Remote Procedure Call',
        'Topic :: System :: Distributed Computing']

    from distutils.command import install
    if len(sys.argv) > 1 and sys.argv[1] == 'bdist_wininst':
        for scheme in install.INSTALL_SCHEMES.values():
            scheme['data'] = scheme['purelib']

        for fileInfo in data_files:
            fileInfo[0] = '..\\PURELIB\\%s' % fileInfo[0]

    setup(**args)

def skel_visit(skel, dirname, names):
    L = []
    for name in names:
        if os.path.isfile(os.path.join(dirname, name)):
            L.append(os.path.join(dirname, name))

    skel.append([os.path.join('hprose', dirname), L])

if __name__ == '__main__':
    main()
