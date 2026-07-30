"""Warstwa aplikacji — przypadki użycia orkiestrujące domenę i porty.

Cienka warstwa: waliduje wejście przez rejestr, buduje agregaty, woła porty
(repozytorium, generator dokumentu). Nie zawiera reguł biznesowych (te są w domenie)
ani szczegółów technicznych (te są w infrastrukturze).
"""
