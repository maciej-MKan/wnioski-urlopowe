"""Warstwa domeny — czysta logika biznesowa urlopów.

Nie zależy od żadnego frameworka (FastAPI, Jinja, WeasyPrint) ani od bazy danych.
Dostęp do świata zewnętrznego opisują wyłącznie *porty* (`ports.py`) — interfejsy,
które implementuje warstwa infrastruktury. Dzięki temu domenę można testować w izolacji.
"""
