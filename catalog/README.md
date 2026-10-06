# Philadelphia Housing and Land Use

![philadelphia](https://img.shields.io/badge/philadelphia-blue) ![pennsylvania](https://img.shields.io/badge/pennsylvania-blue) ![housing](https://img.shields.io/badge/housing-blue) ![zoning](https://img.shields.io/badge/zoning-blue) ![land use](https://img.shields.io/badge/land_use-blue) ![parcels](https://img.shields.io/badge/parcels-blue) ![vacancy](https://img.shields.io/badge/vacancy-blue) ![affordable housing](https://img.shields.io/badge/affordable_housing-blue) ![building footprints](https://img.shields.io/badge/building_footprints-blue) ![urban planning](https://img.shields.io/badge/urban_planning-blue)

Ten collections describing property, zoning, vacancy, and affordable housing in Philadelphia, mirrored from the City of Philadelphia's ArcGIS services via [OpenDataPhilly](https://opendataphilly.org/). Together they answer what exists on a parcel, what the zoning code permits there, whether the city believes it is empty, and what publicly funded housing has been built.

Property parcels, land use, and building footprints cover the whole city. Zoning base districts and overlays record what the code allows, and a lookup table decodes every zoning code. The city's vacancy model flags likely-vacant lots and likely-vacant buildings. Affordable housing production lists DHCD-funded projects completed since 1994 and the units each one delivered. The council districts give each location its political representation.

Each collection ships as GeoParquet in CRS84 (longitude, latitude), with PMTiles for rendering and two to three verified map styles. Start at the catalog [AGENTS.md](AGENTS.md) for join keys, worked queries, and the data quirks that cause most wrong answers.

## Collections

<details>
<summary>📁 10 collections (click to expand)</summary>

### [Affordable Housing Production](affordable_housing/)

Affordable housing projects funded by the Division of Housing and Community Development and completed since 1994. DHCD funds developers to build and maintain affordable units across the city.

### [City Council Districts (2024)](council_districts_2024/)

The ten Philadelphia City Council districts as redrawn after the 2020 census. Each district elects one council member, and the city also seats seven at-large members who represent no district.

### [Property Parcels](dor_parcel/)

Boundaries of every real estate property parcel in Philadelphia, drawn from legally recorded deed documents. The Department of Records maintains the layer and republishes it weekly.

### [Land Use](land_use/)

Land use assigned to each parcel in Philadelphia, maintained by the City Planning Commission. Land use records the activity on the ground, such as residential, commercial, or industrial, rather than what zoning permits.

### [Building Footprints](li_building_footprints/)

Outlines of buildings and related structures across Philadelphia, captured photogrammetrically from aerial imagery. The layer covers residential, commercial, and industrial buildings, along with isolated garages, mobile homes, sheds, greenhouses, silos, and buildings under construction that have walls.

### [Vacant Property Indicators — Buildings](vacant_indicators_bldg/)

Parcels across Philadelphia that the city's Vacant Property Indicators model flags as holding a likely vacant building. It is the structural counterpart to [vacant_indicators_land](../vacant_indicators_land), built by the same inter-agency model.

### [Vacant Property Indicators — Land](vacant_indicators_land/)

Parcels across Philadelphia that the city's Vacant Property Indicators model flags as likely vacant land. The model was built by the Office of Innovation and Technology with Licenses and Inspections, the Office of Property Assessment, the Philadelphia Land Bank, and the Philadelphia Water Department.

### [Zoning Base Districts](zoning_basedistricts/)

Boundaries of Philadelphia's zoning base districts under the zoning code enacted in December 2011 and effective 22 August 2012. A base district sets what may be built on a parcel and how it may be used.

### [Zoning Code Descriptions](zoning_descriptions/)

Zoning Descriptions

### [Zoning Overlays](zoning_overlays/)

Boundaries of Philadelphia's zoning overlay districts, enacted 15 December 2011 and effective 22 August 2012. An overlay adds rules on top of the base district beneath it, so a parcel can sit under several at once.

</details>

## Coverage

The collections cover the City of Philadelphia. Each `collection.json` gives its exact bounding box.

## Source

[https://opendataphilly.org/](https://opendataphilly.org/)

## Processing Notes

Extracted from City of Philadelphia ArcGIS FeatureServer endpoints on 2026-08-26 using `portolan extract arcgis`, one service per collection. Every layer is served from the city's ArcGIS Online organization fLeGjb7u4uXqeF9q. Feature counts were checked against each service's returnCountOnly response, and all ten collections match their source exactly.
The services serve EPSG:3857 (Web Mercator). The GeoParquet is reprojected to CRS84 (longitude, latitude) for all collections, so `ST_Area(geometry)` returns square degrees; reproject to EPSG:2272 to measure. The `Shape__Area` and `Shape__Length` columns keep the publisher's Web Mercator metres.
Column meanings come from three sources. ArcGIS field aliases supplied attested names such as `basereg` = "Base Registry Number". The [PASDA metadata record](https://www.pasda.psu.edu/uci/FullMetadataDisplay.aspx?file=PhiladelphiaBuildings2017.xml) supplied the building footprint FCODE key, which states "1810 = Building 1830 = Tank". The city data team's [post on the OpenDataPhilly forum](https://groups.google.com/g/opendataphilly/c/anMKnNH3pqc) supplied the vacancy rank semantics. Land use category labels were derived from the data; see AGENTS.md for the query.
`zoning_descriptions` is a non-spatial lookup table. `portolan extract arcgis` reports "0/0 layers" for services that advertise a table rather than a layer, so that parquet was written with DuckDB from the same FeatureServer query endpoint. See [portolan-cli#812](https://github.com/portolan-sdi/portolan-cli/issues/812).
The 2026-08-26 extract reordered land use with `gpio sort hilbert` to give its row groups spatial locality.

## Updates and versions

A scheduled job checks every source daily. It re-extracts a collection only when the city edited its rows, and it records a new version only when the rows changed. Each refresh repeats the processing above and sorts every spatial collection with `gpio sort hilbert`. The current data is always at `<collection>/<collection>.parquet`. Each earlier version stays at `<collection>/versions/<version>.parquet` and never changes. Each `collection.json` lists every version with its dates and checksum. The first version of every collection is the 2026-08-26 extract.

The publisher states an update cadence for three collections on OpenDataPhilly. A version is recorded at most once per interval below.

| Collection | Stated cadence | Minimum days between versions |
|---|---|---|
| dor_parcel | Weekly | 7 |
| li_building_footprints | Weekly | 7 |
| council_districts_2024 | As needed | 1 |
| All others | Not stated | 7 |

Each collection carries `updated` (the newest version), `phl:source_updated` (when the city last edited those rows), and `phl:update_frequency`.


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
