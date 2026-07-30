"""Warstwa infrastruktury — adaptery implementujące porty domeny.

Tu żyją szczegóły techniczne: SQLite, Jinja2, WeasyPrint, formatowanie dat po polsku.
Import WeasyPrint jest odizolowany do `pdf.py`, dzięki czemu pozostałe warstwy (i większość
testów) działają bez ciężkich zależności systemowych Pango/Cairo.
"""
