# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

import tomli
from regex import F

sys.path.insert(0, os.path.abspath("../../src"))

# -- Project information -----------------------------------------------------
version = "unknown"
with open("../../src/lyndows/_version.py", "r") as f:
    line = None
    while line != "":
        line = f.readline()
        if line.startswith("__version__"):
            version = line.split()[-1]
            break

with open("../../pyproject.toml", encoding="UTF-8") as strm:
    defn = tomli.loads(strm.read())
    try:
        config = defn.get("project", {})
    except LookupError as err:
        raise IOError("pyproject.toml does not contain a project section") from err

authors = [a["name"] for a in config["authors"]]
project = config["name"]
author = ", ".join(authors)
copyright = author
documentation_summary = config["description"]
release = version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinxcontrib.apidoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.coverage",
    "sphinx.ext.viewcode",
    # 'sphinx.ext.autosummary',
    "sphinx.ext.intersphinx",
    "myst_parser",
]


# sphinx-apidoc is a tool for automatic generation of Sphinx sources that,
# using the autodoc extension, documents a whole package in the style of other
# automatic API documentation tools. sphinx-apidoc does not actually build
# documentation - rather it simply generates it. As a result,
# it must be run before sphinx-build.

# The path to the module to document. This must be a path to a Python package.
# This path can be a path relative to the documentation source directory
# or an absolute path.
apidoc_module_dir = f"../../src/{project}"

# The output directory. If it does not exist, it is created. This path
# is relative to the documentation source directory.
apidoc_output_dir = "api"

# An optional list of modules to exclude. These should be paths relative
# to apidoc_module_dir. fnmatch-style wildcarding is supported.
apidoc_excluded_paths = ["main*", "ui/window*"]

# Put documentation for each module on its own page.
# Otherwise there will be one page per (sub)package.
apidoc_separate_modules = True

# Filename for a table of contents file. Defaults to modules.
# If set to False, apidoc will not create a table of contents file.
apidoc_toc_file = "modules"

# When set to True, put module documentation before submodule documentation.
apidoc_module_first = True

# Extra arguments which will be passed to sphinx-apidoc.
# These are placed after flags and before the module name.
apidoc_extra_args = ["--implicit-namespaces"]

# Functions imported from C modules cannot be introspected, and therefore
# the signature for such functions cannot be automatically determined.
# However, it is an often-used convention to put the signature into the first line
# of the function’s docstring.
# If this boolean value is set to True (which is the default),
# autodoc will look at the first line of the docstring for functions and methods,
# and if it looks like a signature, use the line as the signature and remove
# it from the docstring content.
exclude_members = [
    "__init__",
    "__module__",
    "__weakref__",
    "__dict__",
    "__slots__",
    "__setattr__",
]
autodoc_default_options = {
    "members": True,
    #'ignore-module-all': False,
    "member-order": "bysource",
    "special-members": None,
    "undoc-members": None,
    "exclude-members": ",".join(exclude_members),
    "show-inheritance": True,
    "inherited-members": False,
}
autodoc_docstring_signature = True
autodoc_typehints = "signature"
autodoc_class_signature = "mixed"
# autodoc_member_order = "groupwise"

# Type hints for autodoc
typehints_use_signature = False
typehints_use_signature_returns = False
typehints_fully_qualified = True
always_document_param_types = True
typehints_document_rtypes = True
typehints_use_rtypes = False
typehints_defaults = "braces-after"
simplify_optional_unions = True

# Boolean indicating whether to scan all found documents
# for autosummary directives, and to generate stub pages for each.
# Can also be a list of documents for which stub pages should be generated.
# The new files will be placed in the directories specified in the :toctree:
# options of the directive
autosummary_generate = [f"{project}"]

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = False
napoleon_use_keyword = False
napoleon_use_rtype = False
napoleon_preprocess_types = False
napoleon_type_aliases = False
napoleon_attr_annotations = False

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix of source filenames.
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# A list of ignored prefixes for module index sorting.
modindex_common_prefix = [f"{project}."]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
# exclude_patterns = ['acide.main', 'acide.ui.window']

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "furo"
html_theme_options = {
    "sidebar_hide_name": True,
    "navigation_with_keys": True,
    "top_of_page_button": "edit",  # None
    "dark_logo": "logo.png",
    "light_logo": "logo_light.png",
    "light_css_variables": {
        "font-stack": "'Lucida Grande', 'Lucida Sans Unicode', 'Lucida Sans', Geneva, Verdana, sans-serif",
        "font-stack--monospace": "SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', Courier, monospace",
        #
        "font-size--normal": "100.0%",
        # "font-size--small": "95.0%",  #
        "font-size--small": "100.0%",  # signatures, returns, raises, etc...
        "code-font-size": "85.25%",
        "sidebar-item-font-size": "75%",
        "toc-title-font-size": "75%",
        "toc-font-size--mobile": "75%",
        "sidebar-caption-font-size": "90%",
        "sidebar-search-input-font-size": "90.0%",
        "admonition-font-size": "80.0%",
        "admonition-title-font-size": "0.8rem",
    },
    "dark_css_variables": {
        "font-stack": "'Lucida Grande','Lucida Sans Unicode','Lucida Sans',Geneva,Verdana,sans-serif",
        "font-stack--monospace": "SFMono-Regular,Menlo,Monaco,Consolas,'Liberation Mono','Courier New',Courier,monospace",
        "font-size--normal": "100.0%",
        # "font-size--small": "95.0%",  #
        "font-size--small": "100.0%",  # signatures, returns, raises, etc...
        "code-font-size": "85.25%",
        "sidebar-item-font-size": "75%",
        "toc-title-font-size": "75%",
        "toc-font-size--mobile": "75%",
        "sidebar-caption-font-size": "90%",
        "sidebar-search-input-font-size": "90.0%",
        "admonition-font-size": "80.0%",
        "admonition-title-font-size": "0.8rem",
    },
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
# html_logo = "_static/logo.png"


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [("index", f"{project}.tex", f"{project} Documentation", [f"{author}"], 1)]

# If true, show URL addresses after external links.
# man_show_urls = False
