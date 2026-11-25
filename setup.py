"""Compatibilidad: la configuración canónica vive en pyproject.toml.

``pip install -e .`` usa la sección [project] de pyproject.toml; este shim
evita que herramientas antiguas fallen al leer setup.py.
"""

from setuptools import setup

setup()
