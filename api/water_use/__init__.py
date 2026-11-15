"""Field Shift — algorithme « Water Use ».

Donne à chaque rotation une note eau entre 0 et 1 (plus haut = dépend moins d'une eau rare),
en simulant l'eau du sol jour par jour (un « seau » à deux étages) avec la vraie météo
NASA POWER, le vrai sol (SSURGO aux États-Unis, SoilGrids ailleurs) et la pente SRTM.
Pression sur l'eau : puits USGS, SMAP / ECOSTRESS (NASA Earthdata) ou MERRA-2.
Validation : ERA5.

Méthodes : FAO-56 (Allen et al. 1998), FAO-33/66 (Ky), NRCS TR-55 / NEH 630 ch. 9
(curve numbers), Saxton & Rawls 2006 (réserve d'eau du sol).
"""

__version__ = "0.2.0"
