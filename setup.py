from distutils.core import setup

pkg = 'SystemPlugins.Satscan'
setup (name = 'enigma2-plugin-systemplugins-satscan',
	version = '1.2',
	description = 'Blindscan plugin for DVB-S',
	packages = [pkg],
	package_dir = {pkg: 'plugin'}
)
