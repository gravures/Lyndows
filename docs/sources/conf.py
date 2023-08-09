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

# PROJECT INFORMATION
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

# SPHINX GLOBALS
extensions = [
    "sphinx.ext.autodoc",
    "sphinxcontrib.apidoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.coverage",
    # "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "myst_parser",
]
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
maximum_signature_line_length = 120
add_function_parentheses = True
add_module_names = False
modindex_common_prefix = [f"{project}."]


# SPHINX-CONTRIB-APIDOC
apidoc_module_dir = f"../../src/{project}"
apidoc_output_dir = "api"
apidoc_excluded_paths = ["main*", "ui/window*"]
apidoc_separate_modules = True
apidoc_toc_file = "modules"
apidoc_module_first = True
apidoc_extra_args = ["--implicit-namespaces", "--force"]


# AUTODOC
exclude_members = []
autodoc_default_flags = []
autodoc_default_options = {
    "members": True,
    "ignore-module-all": False,
    "private-members": "",
    "special-members": "",
    "inherited-members": False,
    # "imported-members": "",
    "show-inheritance": False,  # FIXME: unable to hide bases class
    "undoc-members": None,
    "exclude-members": ",".join(exclude_members),
}
autodoc_member_order = "bysource"
autoclass_content = "both"
autodoc_docstring_signature = True
autodoc_class_signature = "mixed"
autodoc_typehints = "signature"
autodoc_typehints_description_target = "all"
autodoc_typehints_format = "short"
autodoc_preserve_defaults = True
autodoc_inherit_docstrings = True


# AUTO-SUMMARY
autosummary_generate = [f"{project}"]


# NAPOLEON
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_keyword = False
napoleon_use_rtype = False
napoleon_preprocess_types = False
napoleon_type_aliases = True
napoleon_attr_annotations = False


# HTML OUTPUT
templates_path = ["_templates"]
html_static_path = ["_static"]
html_theme = "furo"
html_theme_options = {
    "sidebar_hide_name": True,
    "navigation_with_keys": True,
    "top_of_page_button": "edit",  # None
    "dark_logo": "logo.png",
    "light_logo": "logo_light.png",
}


# MAN PAGES
# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [("index", f"{project}.tex", f"{project} Documentation", [f"{author}"], 1)]
# man_show_urls = False
