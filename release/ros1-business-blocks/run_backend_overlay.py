#!/usr/bin/env python3
"""Additive canonical console extension. Start only on an idle deployment."""
import os
from pathlib import Path
import runpy
import sys

site = Path(os.environ['ARES_R_SITE_ROOT']).resolve()
overlay = Path(__file__).resolve().parent
utility = overlay.parent / 'ros1-blocks-center-restore'
sys.path[:0] = [str(overlay), str(utility), str(site / 'src')]
os.environ['PYTHONPATH'] = os.pathsep.join([str(overlay), str(utility), str(site / 'src')])
import ares_r.demos.console
from blocks.console import BusinessConsole

ares_r.demos.console.DemoConsole = BusinessConsole
os.chdir(site)
import ares_r.canonical_backend as backend
from blocks.backend import BusinessBackend
backend.CanonicalBackend = BusinessBackend
backend.main()
