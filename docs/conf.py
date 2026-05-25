"""Sphinx configuration for Astro documentation."""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from astro import __version__  # noqa: E402

project = "Astro"
copyright = "2026, Astro contributors"
author = "Astro contributors"
version = __version__
release = __version__

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

root_doc = "index"

html_theme = "furo"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_title = "Astro pipeline"

# Brand palette:
#   brand-bg          #F2EFE0
#   brand-bg-alt      #F0E8D8
#   brand-primary     #4AA4B6
#   brand-primary-2   #90D0D8
#   brand-accent      #F85800
#   brand-accent-2    #F87818
#   brand-text        #182028
#   brand-text-strong #101820
html_theme_options = {
    "light_logo": "logo.png",
    "dark_logo": "logo.png",
    "light_css_variables": {
        "color-brand-primary": "#4AA4B6",
        "color-brand-content": "#4AA4B6",
        "color-brand-visited": "#F85800",
        "color-foreground-primary": "#101820",
        "color-foreground-secondary": "#182028",
        "color-foreground-muted": "#182028",
        "color-foreground-border": "#90D0D8",
        "color-background-primary": "#FFFFFF",
        "color-background-secondary": "#FFFFFF",
        "color-background-hover": "#F0E8D8",
        "color-background-border": "#90D0D8",
        "color-content-background": "#FFFFFF",
        "color-sidebar-background": "#F2EFE0",
        "color-sidebar-search-background": "#F2EFE0",
        "color-sidebar-search-background--focus": "#F0E8D8",
        "color-sidebar-link-text--top-level": "#4AA4B6",
        "color-toc-background": "#FFFFFF",
        "color-toc-item-text--active": "#4AA4B6",
        "color-highlighted-background": "#90D0D8",
        "color-inline-code-background": "#F0E8D8",
        "color-link--hover": "#F87818",
        "color-link-underline": "transparent",
        "color-link-underline--hover": "transparent",
        "color-link-underline--visited": "transparent",
        "color-link-underline--visited--hover": "transparent",
        "color-header-background": "#FFFFFF",
        "color-header-border": "#90D0D8",
    },
    "dark_css_variables": {
        "color-brand-primary": "#4AA4B6",
        "color-brand-content": "#4AA4B6",
        "color-brand-visited": "#F87818",
        "color-foreground-primary": "#E8E8D8",
        "color-foreground-secondary": "#F0E8D8",
        "color-foreground-muted": "#90D0D8",
        "color-foreground-border": "#10B0D8",
        "color-background-primary": "#101820",
        "color-background-secondary": "#182028",
        "color-background-hover": "#182028",
        "color-background-border": "#10B0D8",
        "color-sidebar-link-text--top-level": "#4AA4B6",
        "color-toc-item-text--active": "#4AA4B6",
        "color-highlighted-background": "#182028",
        "color-inline-code-background": "#182028",
        "color-link--hover": "#F87818",
        "color-link-underline": "transparent",
        "color-link-underline--hover": "transparent",
        "color-link-underline--visited": "transparent",
        "color-link-underline--visited--hover": "transparent",
        "color-header-background": "#101820",
        "color-header-border": "#10B0D8",
    },
}

myst_heading_anchors = 3

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": False,
}

autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "polars": ("https://docs.pola.rs/api/python/stable", None),
    "pydantic": ("https://docs.pydantic.dev/latest", None),
}
