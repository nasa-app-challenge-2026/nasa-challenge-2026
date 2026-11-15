/**
 * Parseurs binaires sécurisés (zéro dépendance externe) avec garde-fous mémoire et validation stricte du format :
 * 1) Les grilles NumPy `.npy` renvoyées par l'API TiTiler Data de Planetary Computer (MODIS NDVI/EVI & USDA CDL).
 * 2) Les rasters GeoTIFF non compressés (`compression=NONE`, `pixelType=U8`) renvoyés par
 *    ArcGIS `ImageServer/exportImage` d'Agriculture et Agroalimentaire Canada (AAC / AAFC).
 */

const MAX_GRID_DIMENSION = 512;
const MAX_BANDS = 8;
const MAX_TOTAL_ELEMENTS = MAX_GRID_DIMENSION * MAX_GRID_DIMENSION * MAX_BANDS;

const BYTES_PER_DTYPE = {
  '<i2': 2,
  '<u2': 2,
  '|u1': 1,
  '<u1': 1,
  '<f4': 4,
};

const TIFF_TYPE_SIZES = {
  1: 1, // BYTE (uint8)
  2: 1, // ASCII
  3: 2, // SHORT (uint16)
  4: 4, // LONG (uint32)
};

function readTiffValueAt(buf, offset, type) {
  if (type === 1 || type === 2) return buf.readUInt8(offset);
  if (type === 3) return buf.readUInt16LE(offset);
  if (type === 4) return buf.readUInt32LE(offset);
  return null;
}

/**
 * Parse un fichier binaire `.npy` (NumPy format 1.0/2.0, C-order 2D/3D) en mémoire avec contrôle strict des bornes.
 * Renvoie `{ shape, descr, width, height, bands }`.
 */
export function parseNpyGrid(buffer, { expectedWidth = null, expectedHeight = null } = {}) {
  const buf = Buffer.isBuffer(buffer) ? buffer : Buffer.from(buffer);
  if (buf.length < 16 || buf[0] !== 0x93 || buf.subarray(1, 6).toString('ascii') !== 'NUMPY') {
    throw new Error('Format .npy invalide (en-tête NUMPY manquant)');
  }

  const major = buf[6];
  if (major !== 1 && major !== 2) {
    throw new Error(`Version d'en-tête .npy non supportée : v${major}.${buf[7]}`);
  }

  const headerOffset = major === 1 ? 10 : 12;
  const headerLen = major === 1 ? buf.readUInt16LE(8) : buf.readUInt32LE(8);
  const dataOffset = headerOffset + headerLen;

  if (headerLen > 4096 || dataOffset > buf.length) {
    throw new Error(`En-tête .npy corrompu ou hors bornes (headerLen=${headerLen})`);
  }

  const headerStr = buf.subarray(headerOffset, dataOffset).toString('latin1');
  const descrMatch = headerStr.match(/'descr':\s*'([^']+)'/);
  const fortranMatch = headerStr.match(/'fortran_order':\s*(True|False)/);
  const shapeMatch = headerStr.match(/'shape':\s*\(([^)]*)\)/);
  if (!descrMatch || !shapeMatch) {
    throw new Error(`En-tête .npy non reconnu : ${headerStr}`);
  }
  if (fortranMatch && fortranMatch[1] === 'True') {
    throw new Error('Grille .npy en ordre Fortran (fortran_order=True) non supportée');
  }

  const descr = descrMatch[1];
  const bytesPerElem = BYTES_PER_DTYPE[descr];
  if (!bytesPerElem) {
    throw new Error(`Type NumPy non supporté : ${descr}`);
  }

  const shape = shapeMatch[1]
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .map(Number);

  if (
    (shape.length !== 2 && shape.length !== 3) ||
    shape.some((d) => !Number.isInteger(d) || d <= 0)
  ) {
    throw new Error(
      `Dimensions .npy invalides (tableau 2D ou 3D attendu) : ${JSON.stringify(shape)}`,
    );
  }

  const [nBands, height, width] = shape.length === 3 ? shape : [1, shape[0], shape[1]];
  if (
    nBands > MAX_BANDS ||
    width > MAX_GRID_DIMENSION ||
    height > MAX_GRID_DIMENSION ||
    nBands * width * height > MAX_TOTAL_ELEMENTS
  ) {
    throw new Error(
      `Dimensions .npy hors limites de sécurité : ${nBands}x${height}x${width}`,
    );
  }

  if (expectedWidth !== null && width !== expectedWidth) {
    throw new Error(
      `Largeur de grille .npy inattendue : reçu ${width}, attendu ${expectedWidth}`,
    );
  }
  if (expectedHeight !== null && height !== expectedHeight) {
    throw new Error(
      `Hauteur de grille .npy inattendue : reçu ${height}, attendu ${expectedHeight}`,
    );
  }

  const nPixels = width * height;
  const requiredBytes = dataOffset + nBands * nPixels * bytesPerElem;
  if (buf.length < requiredBytes) {
    throw new Error(
      `Buffer .npy tronqué : ${buf.length} octets reçus pour ${requiredBytes} attendus`,
    );
  }

  const bands = [];
  for (let b = 0; b < nBands; b++) {
    const arr = new Array(nPixels);
    for (let i = 0; i < nPixels; i++) {
      const idx = b * nPixels + i;
      if (descr === '<i2') {
        arr[i] = buf.readInt16LE(dataOffset + idx * 2);
      } else if (descr === '<u2') {
        arr[i] = buf.readUInt16LE(dataOffset + idx * 2);
      } else if (descr === '|u1' || descr === '<u1') {
        arr[i] = buf.readUInt8(dataOffset + idx);
      } else if (descr === '<f4') {
        arr[i] = buf.readFloatLE(dataOffset + idx * 4);
      }
    }
    bands.push(arr);
  }

  return { shape: [nBands, height, width], descr, width, height, bands };
}

/**
 * Parse un GeoTIFF 8-bit monocanal non compressé (`compression=NONE`, `pixelType=U8`, `SamplesPerPixel=1`, `BitsPerSample=8`)
 * avec respect strict de la spécification TIFF 6.0 (valeurs IFD en ligne vs pointeur) et validation des canaux.
 */
export function parseUncompressedTiffU8(
  buffer,
  { expectedWidth = null, expectedHeight = null } = {},
) {
  const buf = Buffer.isBuffer(buffer) ? buffer : Buffer.from(buffer);
  if (
    buf.length < 16 ||
    buf.subarray(0, 2).toString('ascii') !== 'II' ||
    buf.readUInt16LE(2) !== 42
  ) {
    throw new Error('GeoTIFF invalide ou big-endian non supporté');
  }

  const ifdOffset = buf.readUInt32LE(4);
  if (ifdOffset + 2 > buf.length) {
    throw new Error('Offset IFD GeoTIFF hors bornes');
  }

  const numEntries = buf.readUInt16LE(ifdOffset);
  if (numEntries > 256 || ifdOffset + 2 + numEntries * 12 > buf.length) {
    throw new Error('Table IFD GeoTIFF corrompue ou hors bornes');
  }

  const tags = {};
  for (let i = 0; i < numEntries; i++) {
    const pos = ifdOffset + 2 + i * 12;
    const tag = buf.readUInt16LE(pos);
    const type = buf.readUInt16LE(pos + 2);
    const count = buf.readUInt32LE(pos + 4);
    const valOffset = pos + 8;

    const elemSize = TIFF_TYPE_SIZES[type];
    if (!elemSize || count === 0 || count > 4096) continue;

    const totalByteCount = count * elemSize;
    // Spécification TIFF 6.0 : si la valeur tient sur <= 4 octets, elle est stockée directement à `valOffset`
    const dataPos = totalByteCount <= 4 ? valOffset : buf.readUInt32LE(valOffset);
    if (dataPos + totalByteCount > buf.length) {
      throw new Error(`Tag GeoTIFF ${tag} pointe hors du buffer`);
    }

    if (count === 1) {
      tags[tag] = readTiffValueAt(buf, dataPos, type);
    } else {
      const vals = new Array(count);
      for (let k = 0; k < count; k++) {
        vals[k] = readTiffValueAt(buf, dataPos + k * elemSize, type);
      }
      tags[tag] = vals;
    }
  }

  const width = Number(Array.isArray(tags[256]) ? tags[256][0] : tags[256]);
  const height = Number(Array.isArray(tags[257]) ? tags[257][0] : tags[257]);
  const compression = Number(Array.isArray(tags[259]) ? tags[259][0] : (tags[259] ?? 1));
  if (compression !== 1) {
    throw new Error(`GeoTIFF compressé (code ${compression}) : demander compression=NONE`);
  }

  // Vérification stricte de SamplesPerPixel (tag 277), BitsPerSample (tag 258), Photometric (tag 262) et SampleFormat (tag 339)
  const samplesPerPixel = Number(
    Array.isArray(tags[277]) ? tags[277][0] : (tags[277] ?? 1),
  );
  if (samplesPerPixel !== 1) {
    throw new Error(
      `GeoTIFF multi-bandes non supporté pour les codes cultures (SamplesPerPixel=${samplesPerPixel}, attendu=1)`,
    );
  }

  const bitsPerSampleRaw = tags[258] ?? 8;
  const bitsPerSampleList = Array.isArray(bitsPerSampleRaw)
    ? bitsPerSampleRaw
    : [bitsPerSampleRaw];
  if (bitsPerSampleList.length !== 1 || bitsPerSampleList[0] !== 8) {
    throw new Error(
      `GeoTIFF non 8-bit rejeté (BitsPerSample=${JSON.stringify(bitsPerSampleRaw)}, attendu=8)`,
    );
  }

  const photometric = Number(Array.isArray(tags[262]) ? tags[262][0] : (tags[262] ?? 1));
  if (photometric === 2) {
    throw new Error('GeoTIFF RGB (PhotometricInterpretation=2) rejeté : raster thématique U8 attendu');
  }

  const sampleFormatRaw = tags[339] ?? 1;
  const sampleFormat = Number(Array.isArray(sampleFormatRaw) ? sampleFormatRaw[0] : sampleFormatRaw);
  if (sampleFormat !== 1) {
    throw new Error(
      `Format d'échantillon GeoTIFF non supporté (SampleFormat=${sampleFormat}, attendu=1 uint8)`,
    );
  }

  if (
    !Number.isInteger(width) ||
    !Number.isInteger(height) ||
    width <= 0 ||
    height <= 0 ||
    width > MAX_GRID_DIMENSION ||
    height > MAX_GRID_DIMENSION
  ) {
    throw new Error(`Dimensions GeoTIFF invalides ou hors limites : ${width}x${height}`);
  }

  if (expectedWidth !== null && width !== expectedWidth) {
    throw new Error(
      `Largeur GeoTIFF inattendue : reçu ${width}, attendu ${expectedWidth}`,
    );
  }
  if (expectedHeight !== null && height !== expectedHeight) {
    throw new Error(
      `Hauteur GeoTIFF inattendue : reçu ${height}, attendu ${expectedHeight}`,
    );
  }

  const pixels = new Array(width * height).fill(0);

  // Cas 1 : TIFF tuilé (TileWidth = 322, TileOffsets = 324)
  if (tags[324] !== undefined) {
    const tileWidth = Number(tags[322]) || width;
    const tileHeight = Number(tags[323]) || height;
    if (
      tileWidth <= 0 ||
      tileHeight <= 0 ||
      tileWidth > MAX_GRID_DIMENSION * 2 ||
      tileHeight > MAX_GRID_DIMENSION * 2
    ) {
      throw new Error(`Dimensions de tuile GeoTIFF invalides : ${tileWidth}x${tileHeight}`);
    }
    const tileOffsets = Array.isArray(tags[324]) ? tags[324] : [tags[324]];
    const tilesAcross = Math.ceil(width / tileWidth);

    for (let t = 0; t < tileOffsets.length; t++) {
      const tOffset = Number(tileOffsets[t]);
      if (!Number.isFinite(tOffset) || tOffset < 0 || tOffset >= buf.length) {
        throw new Error('Offset de tuile GeoTIFF hors bornes du buffer');
      }
      const tileCol = t % tilesAcross;
      const tileRow = Math.floor(t / tilesAcross);

      for (let r = 0; r < tileHeight; r++) {
        const imgRow = tileRow * tileHeight + r;
        if (imgRow >= height) break;
        for (let c = 0; c < tileWidth; c++) {
          const imgCol = tileCol * tileWidth + c;
          if (imgCol >= width) break;
          const bytePos = tOffset + r * tileWidth + c;
          if (bytePos < buf.length) {
            pixels[imgRow * width + imgCol] = buf[bytePos];
          }
        }
      }
    }
    return { width, height, pixels };
  }

  // Cas 2 : TIFF en bandes (StripOffsets = 273)
  if (tags[273] === undefined || tags[279] === undefined) {
    throw new Error('GeoTIFF invalide : ni TileOffsets (324) ni StripOffsets (273) présents');
  }
  const stripOffsets = Array.isArray(tags[273]) ? tags[273] : [tags[273]];
  const stripByteCounts = Array.isArray(tags[279]) ? tags[279] : [tags[279]];
  let outIdx = 0;
  for (let s = 0; s < stripOffsets.length; s++) {
    const off = Number(stripOffsets[s]);
    const len = Number(stripByteCounts[s]);
    if (!Number.isFinite(off) || !Number.isFinite(len) || off < 0 || off + len > buf.length) {
      throw new Error('Bande GeoTIFF (StripOffset) hors bornes du buffer');
    }
    for (let k = 0; k < len && outIdx < pixels.length; k++) {
      pixels[outIdx++] = buf[off + k];
    }
  }
  return { width, height, pixels };
}
