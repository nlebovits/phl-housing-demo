# Philadelphia Housing and Land Use

![philadelphia](https://img.shields.io/badge/philadelphia-blue) ![pennsylvania](https://img.shields.io/badge/pennsylvania-blue) ![housing](https://img.shields.io/badge/housing-blue) ![zoning](https://img.shields.io/badge/zoning-blue) ![land use](https://img.shields.io/badge/land_use-blue) ![parcels](https://img.shields.io/badge/parcels-blue) ![vacancy](https://img.shields.io/badge/vacancy-blue) ![affordable housing](https://img.shields.io/badge/affordable_housing-blue) ![building footprints](https://img.shields.io/badge/building_footprints-blue) ![urban planning](https://img.shields.io/badge/urban_planning-blue)

Ten collections describing property, zoning, vacancy, and affordable housing in Philadelphia, mirrored from the City of Philadelphia's ArcGIS services via [OpenDataPhilly](https://opendataphilly.org/). Together they answer what exists on a parcel, what the zoning code permits there, whether the city believes it is empty, and what publicly funded housing has been built.

The catalog holds 1,780,845 features. Property parcels (607,957), land use (559,077), and building footprints (546,083) cover the whole city. Zoning base districts (29,205) and overlays (195) record what the code allows, and a 39-row lookup table decodes every zoning code. The city's vacancy model flags 28,737 likely-vacant lots and 9,041 likely-vacant buildings. Affordable housing production lists 501 DHCD-funded projects delivering 19,249 units since 1994.

Each collection ships as GeoParquet in the source CRS, EPSG:3857, with PMTiles for rendering and two to three verified map styles. Start at the catalog [AGENTS.md](AGENTS.md) for join keys, worked queries, and the data quirks that cause most wrong answers.

## Collections

<details>
<summary>📁 10 collections (click to expand)</summary>

### [Affordable Housing Production](phl-housing-demo/affordable_housing/)

Affordable housing projects funded by the Division of Housing and Community Development and completed since 1994. DHCD funds developers to build and maintain affordable units across the city.

501 ...

### [City Council Districts (2024)](phl-housing-demo/council_districts_2024/)

The ten Philadelphia City Council districts as redrawn after the 2020 census. Each district elects one council member, and the city also seats seven at-large members who represent no district.

Use...

### [Property Parcels](phl-housing-demo/dor_parcel/)

Boundaries of every real estate property parcel in Philadelphia, drawn from legally recorded deed documents. The Department of Records maintains the layer and republishes it weekly.

607,957 polygo...

### [Land Use](phl-housing-demo/land_use/)

Land use assigned to each parcel in Philadelphia, maintained by the City Planning Commission. Land use records the activity on the ground, such as residential, commercial, or industrial, rather tha...

### [Building Footprints](phl-housing-demo/li_building_footprints/)

Outlines of buildings and related structures across Philadelphia, captured photogrammetrically from aerial imagery. The layer covers residential, commercial, and industrial buildings, along with is...

### [Vacant Property Indicators — Buildings](phl-housing-demo/vacant_indicators_bldg/)

Parcels across Philadelphia that the city's Vacant Property Indicators model flags as holding a likely vacant building. It is the structural counterpart to [vacant_indicators_land](../vacant_indica...

### [Vacant Property Indicators — Land](phl-housing-demo/vacant_indicators_land/)

Parcels across Philadelphia that the city's Vacant Property Indicators model flags as likely vacant land. The model was built by the Office of Innovation and Technology with Licenses and Inspection...

### [Zoning Base Districts](phl-housing-demo/zoning_basedistricts/)

Boundaries of Philadelphia's zoning base districts under the zoning code enacted in December 2011 and effective 22 August 2012. A base district sets what may be built on a parcel and how it may be ...

### [Zoning Code Descriptions](phl-housing-demo/zoning_descriptions/)

The city's own decoder for Philadelphia zoning district codes. 39 rows pair a code such as `RSA-5` with its written name, "Residential Single-Family Attached-5".

This is a lookup table with no geo...

### [Zoning Overlays](phl-housing-demo/zoning_overlays/)

Boundaries of Philadelphia's zoning overlay districts, enacted 15 December 2011 and effective 22 August 2012. An overlay adds rules on top of the base district beneath it, so a parcel can sit under...

</details>

## Coverage

**Spatial Extent**

- West: -75.2844, South: 39.8596, East: -74.9555, North: 40.1379

## Source

[https://opendataphilly.org/](https://opendataphilly.org/)

## Processing Notes

Extracted from City of Philadelphia ArcGIS FeatureServer endpoints on 2026-08-26 using `portolan extract arcgis`, one service per collection. Every layer is served from the city's ArcGIS Online organization fLeGjb7u4uXqeF9q. Feature counts were checked against each service's returnCountOnly response, and all ten collections match their source exactly.
GeoParquet keeps the source CRS, EPSG:3857 (Web Mercator), for all collections. PMTiles are reprojected to Web Mercator for rendering.
Column meanings come from three sources. ArcGIS field aliases supplied attested names such as `basereg` = "Base Registry Number". The [PASDA metadata record](https://www.pasda.psu.edu/uci/FullMetadataDisplay.aspx?file=PhiladelphiaBuildings2017.xml) supplied the building footprint FCODE key, which states "1810 = Building 1830 = Tank". The city data team's [post on the OpenDataPhilly forum](https://groups.google.com/g/opendataphilly/c/anMKnNH3pqc) supplied the vacancy rank semantics. Land use category labels were derived from the data; see AGENTS.md for the query.
`zoning_descriptions` is a non-spatial lookup table. `portolan extract arcgis` reports "0/0 layers" for services that advertise a table rather than a layer, so that parquet was written with DuckDB from the same FeatureServer query endpoint. See [portolan-cli#812](https://github.com/portolan-sdi/portolan-cli/issues/812).
Land use was reordered with `gpio sort hilbert` to give its row groups spatial locality.


## Citation

City of Philadelphia (2026). Philadelphia Housing and Land Use. Retrieved from OpenDataPhilly. Mirrored on Source Cooperative at https://source.coop/nlebovits/phl-housing-demo.


## Attribution

City of Philadelphia

## License

[other](https://metadata.phila.gov/#help/help-faqs/what-are-the-terms-of-use/)

## Contact

Nissim Lebovits <nissim.lebovits@radiant.earth>

---

*Generated by [Portolan](https://github.com/portolan-sdi/portolan-cli) from STAC metadata and .portolan/metadata.yaml*
