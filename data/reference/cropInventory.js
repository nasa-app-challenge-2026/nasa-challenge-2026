/**
 * Classes of the Annual Crop Inventory of Agriculture and Agri-Food Canada
 * (30 m, every year since 2009). Codes, French labels and colours come from the
 * official table aci_crop_classifications_iac_classifications_des_cultures.csv.
 *
 * `group` sorts the classes for the fire page: cultivated land, grass, forest,
 * burnt area (code 60, added to the inventory from the federal fire perimeters),
 * built-up land, water, and the rest. `crop` maps a class to the app's own
 * catalogue (data/reference/crops.js) when there is a direct match.
 */
const ROWS = [
  [10, 'Nuages', '#000000', 'autre'],
  [20, 'Eau', '#3333FF', 'eau'],
  [30, 'Sol nu', '#996666', 'autre'],
  [34, 'Milieu urbain ou bâti', '#CC6699', 'urbain'],
  [35, 'Serres', '#E1E1E1', 'urbain'],
  [50, 'Arbustaie', '#FFFF00', 'foret'],
  [60, 'Zone brûlée', '#666666', 'brule'],
  [80, 'Terres humides', '#993399', 'eau'],
  [85, 'Tourbière exploitée', '#501B50', 'eau'],
  [110, 'Prairies', '#CCCC00', 'prairie'],
  [120, 'Agriculture (indifférenciée)', '#CC6600', 'culture'],
  [121, 'Terres cultivées', '#FF9933', 'culture'],
  [122, 'Pâturage et fourrages', '#FFCC33', 'prairie', 'foin'],
  [130, 'Trop humide pour semer', '#7899F6', 'culture'],
  [131, 'Jachère', '#FF9900', 'culture'],
  [132, 'Céréales', '#660000', 'culture'],
  [133, 'Orge', '#DAE31D', 'culture', 'orge'],
  [134, 'Autres céréales', '#99CC00', 'culture'],
  [135, 'Millet', '#D2DB25', 'culture'],
  [136, 'Avoine', '#D1D52B', 'culture', 'avoine'],
  [137, 'Seigle', '#CACE32', 'culture', 'seigle'],
  [138, 'Épeautre', '#C3C63A', 'culture'],
  [139, 'Triticale', '#B9BC44', 'culture'],
  [140, 'Blé', '#A7B34D', 'culture'],
  [141, 'Panic érigé', '#B9C64E', 'culture'],
  [142, 'Sorgho', '#999900', 'culture'],
  [143, 'Quinoa', '#E9E2B1', 'culture'],
  [145, 'Blé d’hiver', '#809769', 'culture', 'ble-automne'],
  [146, 'Blé de printemps', '#92A55B', 'culture'],
  [147, 'Maïs-grain', '#FFFF99', 'culture', 'mais'],
  [148, 'Tabac', '#98887C', 'culture'],
  [149, 'Ginseng', '#799B93', 'culture'],
  [150, 'Oléagineux', '#5EA263', 'culture'],
  [151, 'Bourrache', '#52AE77', 'culture'],
  [152, 'Caméline', '#41BF7A', 'culture'],
  [153, 'Canola', '#D6FF70', 'culture', 'canola'],
  [154, 'Lin', '#8C8CFF', 'culture'],
  [155, 'Moutarde', '#D6CC00', 'culture'],
  [156, 'Carthame', '#FF7F00', 'culture'],
  [157, 'Tournesol', '#315491', 'culture'],
  [158, 'Soya', '#CC9933', 'culture', 'soya'],
  [159, 'Autres oléagineux', '#5EA296', 'culture'],
  [160, 'Légumineuses', '#896E43', 'culture'],
  [161, 'Autres légumineuses', '#996633', 'culture'],
  [162, 'Pois', '#8F6C3D', 'culture', 'pois'],
  [163, 'Pois chiche', '#B6A472', 'culture'],
  [167, 'Haricots', '#82654A', 'culture', 'haricot-sec'],
  [168, 'Féveroles', '#A39069', 'culture'],
  [174, 'Lentilles', '#B85900', 'culture'],
  [175, 'Légumes', '#B74B15', 'culture'],
  [176, 'Tomates', '#FF8A8A', 'culture', 'tomate'],
  [177, 'Pomme de terre', '#FFCCCC', 'culture', 'pomme-de-terre'],
  [178, 'Betterave à sucre', '#6F55CA', 'culture'],
  [179, 'Autres légumes', '#FFCCFF', 'culture'],
  [180, 'Fruits', '#DC5424', 'culture'],
  [181, 'Petits fruits', '#D05A30', 'culture'],
  [182, 'Bleuet', '#D20000', 'culture'],
  [183, 'Canneberge', '#CC0000', 'culture'],
  [185, 'Autres baies', '#DC3200', 'culture'],
  [188, 'Vergers', '#FF6666', 'culture'],
  [189, 'Autres fruits', '#C5453B', 'culture'],
  [190, 'Vignobles', '#7442BD', 'culture'],
  [191, 'Houblon', '#FFCC99', 'culture'],
  [192, 'Gazon en plaques', '#B5FB05', 'prairie'],
  [193, 'Fines herbes', '#CCFF05', 'culture'],
  [194, 'Pépinière', '#07F98C', 'culture'],
  [195, 'Sarrasin', '#00FFCC', 'culture', 'sarrasin'],
  [196, 'Graines à canaris', '#CC33CC', 'culture'],
  [197, 'Chanvre', '#8E7672', 'culture'],
  [198, 'Vesce', '#B1954F', 'culture'],
  [199, 'Autres cultures', '#749A66', 'culture'],
  [200, 'Forêt', '#009900', 'foret'],
  [210, 'Forêt de conifères', '#006600', 'foret'],
  [220, 'Forêt de feuillus', '#00CC00', 'foret'],
  [230, 'Forêt mixte', '#CC9900', 'foret'],
];

export const ACI_CLASSES = Object.fromEntries(
  ROWS.map(([code, label, color, group, crop]) => [
    code,
    { code, label, color, group, crop: crop ?? null },
  ]),
);

/** Code of the "burnt area" class. */
export const ACI_BURNT = 60;

/** First and last year published by AAFC. */
export const ACI_FIRST_YEAR = 2009;
export const ACI_LAST_YEAR = 2025;

/** Class of a raw inventory value ("147", 147, "NoData"…), or null. */
export function aciClass(value) {
  const code = Number(value);
  return Number.isFinite(code) ? (ACI_CLASSES[code] ?? null) : null;
}
