# Build project documentation

sphinx_build = find_program('sphinx-build', required: true)
if not sphinx_build.found()
	error('Error: sphinx-build not found, cannot build documentation')
else
	sphinx_version = run_command(sphinx_build, '--version').stdout()
	message(sphinx_version)
endif

message('Building project documentation')
returned = run_command(
	sphinx_build,
	'-v',
	'-b', 'html',
	'sources',
	'build'
)
message(returned.stdout())
message(returned.stderr())

install_subdir(
	'build/html',
	exclude_directories: [],
	exclude_files: [],
	install_dir: join_paths(get_option('datadir'), 'doc/lyndows'),
	strip_directory: true
)

