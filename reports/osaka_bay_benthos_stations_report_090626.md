# Osaka Bay Benthos and Water Quality Monitoring Stations Report

**Date:** June 9, 2026  
**Subject:** Location mapping and spatial overlap analysis of the macrobenthos and water quality monitoring networks in Osaka Bay.  
**Related Script:** [map_osaka_bay_stations.py](file:///home/reyha/SIS_Analysis_WSL/scripts/map_osaka_bay_stations.py)  
**Generated Map:** `figures/osaka_bay_benthos_stations.png`

---

## 1. Background & Objective

Integrating biological survey data with physical water quality metrics is essential for analyzing the impacts of hypoxia on benthic ecosystems in Osaka Bay. However, the macrobenthos database (`benthos_2023.xlsx`) and the processed water quality database (`merged_gdf.feather`) are compiled by different entities and lack direct spatial primary keys. 

The objective of this report is to document the methodology used to resolve the spatial locations of the macrobenthos sampling stations, identify which stations lie in Osaka Bay, and evaluate their overlap with the broader Osaka Bay water quality monitoring network.

---

## 2. Dataset Descriptions

### A. Macrobenthos Database
* **File Path:** `data/raw/benthos_data/benthos_2023.xlsx` (Sheet: `底生生物_累積2023`)
* **Spatial Attributes:** Prefecture Code (`県コード`, Japanese: *Ken-kōdo*) and Serial Number (`連番`, Japanese: *Renban*). No direct latitude or longitude coordinates are provided in this file.
* **Scope:** National dataset containing 48 unique stations across several prefectures in Japan (including Tokyo, Chiba, Kumamoto, Nagasaki, Hiroshima, Osaka, and Hyogo).

### B. Water Quality Database
* **File Path:** `data/processed/merged_gdf.feather`
* **Spatial Attributes:** Prefecture Identifier (`prefectuei`), Serial Number (`renban`), Latitude (`latitude`), Longitude (`longitude`), Zettaicode (`zettaicode`), and Region Division (`division`).
* **Scope:** Regional dataset of the Seto Inland Sea (SIS) containing multi-decadal physical parameters (temperature, salinity, bottom dissolved oxygen) across multiple sea divisions.

---

## 3. Location Mapping Methodology

To obtain latitude and longitude coordinates for the benthos samples:
1. **Index Cleaning:** Cleaned and cast the spreadsheet's `県コード` (Prefecture Code) and `連番` (Serial Number) to numeric values (`ken` and `ten`).
2. **Key Cross-Referencing:** Merged the benthos dataset with the unique stations from `merged_gdf.feather` using the join condition:
   $$\text{benthos\_df.ken} = \text{wq\_gdf.prefectuei} \quad \text{and} \quad \text{benthos\_df.ten} = \text{wq\_gdf.renban}$$
3. **Region Filtering:** Screened the merged dataset to keep only stations classified under `division == 'Osaka Bay'`.

### Osaka & Hyogo Prefecture Station Screening
Out of the 48 unique national stations in the benthos database, only **4 stations** belong to Osaka (27) or Hyogo (28) prefectures. When merged with the coordinate lookup table, they map as follows:

| Station ID | Prefecture Code (`ken`) | Serial Number (`ten`) | Division | Latitude | Longitude | Status |
|:---|---:|---:|:---|---:|---:|:---|
| **27-2** | 27 | 2 | **Osaka Bay** | 34.658333 | 135.409167 | Included |
| **27-44** | 27 | 44 | **Osaka Bay** | 34.439722 | 135.137222 | Included |
| **28-23** | 28 | 23 | **Osaka Bay** | 34.658333 | 135.263889 | Included |
| **28-143** | 28 | 143 | **Harima Nada** | 34.603333 | 134.613889 | Excluded (Outside Osaka Bay) |

Therefore, exactly **3 stations** in the macrobenthos database are located within the geographic boundaries of Osaka Bay.

---

## 4. Osaka Bay Benthos Stations Inventory

The 3 matched stations in Osaka Bay represent **100 total samples** spanning a 17-year period from **2007 to 2024**. The samples are evenly distributed across the stations:

| Station ID | Prefecture Code | Serial Number | Zettaicode | Latitude | Longitude | Sample Count | Sampling Period |
|:---|---:|---:|:---|---:|---:|---:|:---|
| **27-2** | 27 | 2 | `00000272` | 34.658333 | 135.409167 | 34 | 2007 – 2024 |
| **27-44** | 27 | 44 | `00002744` | 34.439722 | 135.137222 | 34 | 2007 – 2024 |
| **28-23** | 28 | 23 | `00002823` | 34.658333 | 135.263889 | 32 | 2007 – 2024 |

*Note: All three stations feature continuous semi-annual data collection, making them highly suitable for long-term ecological trend analysis.*

---

## 5. Network Overlap & Spatial Distribution

A comparison of the datasets reveals that Osaka Bay contains **10 standard water quality monitoring stations**, but only **3 of them** have corresponding macrobenthos data. 

### Overlap Classification:

```
Osaka Bay Monitoring Stations (10 Total)
 ├── Macrobenthos & Water Quality Overlap (3 Stations)
 │    ├── St. 27-2   (Northeastern Inner Bay / Osaka Harbor)
 │    ├── St. 28-23  (Northern Bay / Kobe Coast)
 │    └── St. 27-44  (Southern Bay / Kansai Airport Coast)
 │
 └── Water Quality Only (7 Stations)
      ├── St. 28-11  (Northern Bay / Kobe Shore)
      ├── St. 27-5   (Eastern Bay / Sakai-Seno Coast)
      ├── St. 27-25  (Southeastern Inner Bay)
      ├── St. 27-37  (Southern Outer Bay / Izumisano Coast)
      ├── St. 27-50  (Southwestern Bay / near Awaji Island)
      ├── St. 27-58  (Kitan Strait Boundary / Entrance to Pacific)
      └── St. 28-48  (Akashi Strait Boundary / Western Exit)
```

### Geographical Shading & Exposure Context:
* **St. 27-2 (Osaka Harbor)**: Located in the shallow, semi-enclosed northeastern head of the bay. This area experiences heavy freshwater inputs from the Yodo River, strong stratification, and high nutrient load, making it highly susceptible to seasonal hypoxia.
* **St. 28-23 (Kobe Coast)**: Positioned in the northern part of the bay. It experiences moderate flushing due to its proximity to the Akashi Strait but still suffers from summer oxygen depletion.
* **St. 27-44 (Kansai Airport Coast)**: Located in the southern, wider portion of the bay. Water exchange is higher here due to open communication with the Kitan Strait (Pacific Ocean), generally leading to shorter and less severe hypoxic exposure compared to St. 27-2.

---

## 6. Visualization & Map Standards

A spatial map representing this network overlap has been generated and saved to:
`figures/osaka_bay_benthos_stations.png`

The map was generated using the **Setonaikai High-Resolution Land Boundary Shapefile (`Setonaikai_boundary_2.shp`)** and conforms to the following project mapping specifications:
* **Ocean Facecolor:** `lightblue` (allows narrow straits and inner bays to be filled correctly).
* **Land Color & Edges:** `lightgray` land fill with a `black` border of width `0.5` (Z-Order: 1).
* **Gridlines:** Plotted with coordinate labels, dashed lines (`--`), and 50% transparency (Z-Order: 2).
* **WQ-Only Stations:** Represented as dimgray circles (Size: 100, Z-Order: 3).
* **WQ & Benthos Stations:** Represented as highlighted red stars (Size: 250, Z-Order: 5) and marked with distinct yellow labels (`St. 27-2 (Benthos)`, etc.) to ensure instant readability.
* **Extent Crop:** Dynamic bounding box set to `[134.8, 135.6, 34.15, 34.85]` under EPSG:4326 PlateCarree projection.

---

## 7. Conclusions & Recommendations

1. **Direct Spatial-Temporal Linking**: The 3 matched benthos stations (St. 27-2, St. 27-44, and St. 28-23) line up perfectly with active long-term water quality monitoring sites. This enables exact temporal matching of biological samples with physical variables (e.g., matching a August 2015 benthos abundance sample with the actual August 2015 bottom DO measurement at the same station).
2. **Spatial Interpolation Support**: For the remaining 7 WQ-only stations, bottom DO values can be interpolated (e.g., via Ordinary Kriging with bathymetric masking) to reconstruct historical hypoxic zone fields. This allows the model to estimate hypoxic exposure frequencies for benthos stations even during seasons when direct water quality data at those specific sites might be sparse.
3. **Data Integrity Check**: The 100 matching samples have clean dates and integer-valued station keys. During downstream analysis, care should be taken to handle the wide format of the species columns in `benthos_2023.xlsx` (melting from wide to long format to compute Shannon diversity and richness indexes).
