from distutils.core import setup

pkg = 'SystemPlugins.Satscan'
setup (name = 'enigma2-plugin-systemplugins-satscan',
	version = '0.2',
	description = 'Alternative blindscan plugin, currently only for VU+',
	packages = [pkg],
	package_dir = {pkg: 'plugin'}
)
