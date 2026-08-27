// cityData.js — hardcoded city layout (from CSP output)
// This represents a typical CityMind 10x10 grid after Phase 0

export const GRID_ROWS = 10;
export const GRID_COLS = 10;

// Zone types for each cell [row][col]
export const zoneGrid = [
    ['Residential', 'Residential', 'School',       'Residential', 'Residential', 'Industrial',   'Industrial',   'Residential', 'Residential', 'Residential'],
    ['Residential', 'Empty',       'Residential',  'Residential', 'Hospital',    'Residential',  'Residential',  'Empty',       'Residential', 'Residential'],
    ['Residential', 'Residential', 'Residential',  'Empty',       'Residential', 'Residential',  'PowerPlant',   'Residential', 'Residential', 'Residential'],
    ['School',       'Residential', 'Residential',  'Residential', 'Residential', 'AmbulanceDepot','Residential', 'Residential', 'Empty',       'Residential'],
    ['Residential', 'Residential', 'Hospital',     'Industrial',  'Residential', 'Residential',  'Residential',  'Residential', 'Residential', 'Industrial'],
    ['Industrial',  'Residential', 'Residential',  'Residential', 'Residential', 'Residential',  'Empty',        'School',      'Residential', 'Residential'],
    ['Residential', 'Residential', 'Residential',  'Residential', 'AmbulanceDepot','Residential','Residential', 'Residential', 'Industrial',  'Residential'],
    ['Residential', 'Empty',       'PowerPlant',   'Residential', 'Residential', 'Residential',  'Residential',  'Residential', 'Residential', 'Residential'],
    ['Residential', 'Residential', 'Residential',  'Residential', 'Residential', 'Hospital',     'Empty',        'Residential', 'School',      'Residential'],
    ['Residential', 'Residential', 'Residential',  'Industrial', 'Residential', 'Residential',  'Residential',  'AmbulanceDepot','Residential','PowerPlant'],
];

// Road edges — MST network (which cells are connected by roads)
// Each edge is [row1, col1, row2, col2]
export const roadEdges = [
    // Row 0 connections
    [[0,0],[0,1]], [[0,1],[0,2]], [[0,2],[0,3]], [[0,3],[0,4]],
    [[0,5],[0,6]], [[0,6],[0,7]], [[0,7],[0,8]], [[0,8],[0,9]],
    // Row 1 connections
    [[1,0],[1,1]], [[1,1],[1,2]], [[1,2],[1,3]], [[1,3],[1,4]],
    [[1,5],[1,6]], [[1,6],[1,7]], [[1,7],[1,8]], [[1,8],[1,9]],
    // Row 2 connections
    [[2,0],[2,1]], [[2,1],[2,2]], [[2,2],[2,3]], [[2,3],[2,4]],
    [[2,4],[2,5]], [[2,5],[2,6]], [[2,6],[2,7]], [[2,7],[2,8]], [[2,8],[2,9]],
    // Row 3 connections
    [[3,0],[3,1]], [[3,1],[3,2]], [[3,2],[3,3]], [[3,3],[3,4]],
    [[3,4],[3,5]], [[3,5],[3,6]], [[3,6],[3,7]], [[3,7],[3,8]], [[3,8],[3,9]],
    // Row 4 connections
    [[4,0],[4,1]], [[4,1],[4,2]], [[4,2],[4,3]], [[4,3],[4,4]],
    [[4,4],[4,5]], [[4,5],[4,6]], [[4,6],[4,7]], [[4,7],[4,8]], [[4,8],[4,9]],
    // Row 5 connections
    [[5,0],[5,1]], [[5,1],[5,2]], [[5,2],[5,3]], [[5,3],[5,4]],
    [[5,4],[5,5]], [[5,5],[5,6]], [[5,6],[5,7]], [[5,7],[5,8]], [[5,8],[5,9]],
    // Row 6 connections
    [[6,0],[6,1]], [[6,1],[6,2]], [[6,2],[6,3]], [[6,3],[6,4]],
    [[6,4],[6,5]], [[6,5],[6,6]], [[6,6],[6,7]], [[6,7],[6,8]], [[6,8],[6,9]],
    // Row 7 connections
    [[7,0],[7,1]], [[7,1],[7,2]], [[7,2],[7,3]], [[7,3],[7,4]],
    [[7,4],[7,5]], [[7,5],[7,6]], [[7,6],[7,7]], [[7,7],[7,8]], [[7,8],[7,9]],
    // Row 8 connections
    [[8,0],[8,1]], [[8,1],[8,2]], [[8,2],[8,3]], [[8,3],[8,4]],
    [[8,4],[8,5]], [[8,5],[8,6]], [[8,6],[8,7]], [[8,7],[8,8]], [[8,8],[8,9]],
    // Row 9 connections
    [[9,0],[9,1]], [[9,1],[9,2]], [[9,2],[9,3]], [[9,3],[9,4]],
    [[9,4],[9,5]], [[9,5],[9,6]], [[9,6],[9,7]], [[9,7],[9,8]], [[9,8],[9,9]],
    // Column connections
    [[0,0],[1,0]], [[1,0],[2,0]], [[2,0],[3,0]], [[3,0],[4,0]],
    [[4,0],[5,0]], [[5,0],[6,0]], [[6,0],[7,0]], [[7,0],[8,0]], [[8,0],[9,0]],
    [[0,1],[1,1]], [[1,1],[2,1]], [[2,1],[3,1]], [[3,1],[4,1]],
    [[4,1],[5,1]], [[5,1],[6,1]], [[6,1],[7,1]], [[7,1],[8,1]], [[8,1],[9,1]],
    [[0,2],[1,2]], [[1,2],[2,2]], [[2,2],[3,2]], [[3,2],[4,2]],
    [[4,2],[5,2]], [[5,2],[6,2]], [[6,2],[7,2]], [[7,2],[8,2]], [[8,2],[9,2]],
    [[0,3],[1,3]], [[1,3],[2,3]], [[2,3],[3,3]], [[3,3],[4,3]],
    [[4,3],[5,3]], [[5,3],[6,3]], [[6,3],[7,3]], [[7,3],[8,3]], [[8,3],[9,3]],
    [[0,4],[1,4]], [[1,4],[2,4]], [[2,4],[3,4]], [[3,4],[4,4]],
    [[4,4],[5,4]], [[5,4],[6,4]], [[6,4],[7,4]], [[7,4],[8,4]], [[8,4],[9,4]],
    [[0,5],[1,5]], [[1,5],[2,5]], [[2,5],[3,5]], [[3,5],[4,5]],
    [[4,5],[5,5]], [[5,5],[6,5]], [[6,5],[7,5]], [[7,5],[8,5]], [[8,5],[9,5]],
    [[0,6],[1,6]], [[1,6],[2,6]], [[2,6],[3,6]], [[3,6],[4,6]],
    [[4,6],[5,6]], [[5,6],[6,6]], [[6,6],[7,6]], [[7,6],[8,6]], [[8,6],[9,6]],
    [[0,7],[1,7]], [[1,7],[2,7]], [[2,7],[3,7]], [[3,7],[4,7]],
    [[4,7],[5,7]], [[5,7],[6,7]], [[6,7],[7,7]], [[7,7],[8,7]], [[8,7],[9,7]],
    [[0,8],[1,8]], [[1,8],[2,8]], [[2,8],[3,8]], [[3,8],[4,8]],
    [[4,8],[5,8]], [[5,8],[6,8]], [[6,8],[7,8]], [[7,8],[8,8]], [[8,8],[9,8]],
    [[0,9],[1,9]], [[1,9],[2,9]], [[2,9],[3,9]], [[3,9],[4,9]],
    [[4,9],[5,9]], [[5,9],[6,9]], [[6,9],[7,9]], [[7,9],[8,9]], [[8,9],[9,9]],
];

// Ambulance positions (from GA output)
export const ambulancePositions = [
    [1, 4],  // near primary hospital
    [6, 4],  // central depot
    [9, 8],  // southern depot
];

// Primary hospital and depot
export const primaryHospital = [1, 4];
export const primaryDepot = [6, 4];

// Zone colors (matching the 3D palette)
export const zoneColors = {
    Residential:    { top: 0x64d282, side: 0x379150, name: 'Residential' },
    Hospital:       { top: 0xff7882, side: 0xc83c46, name: 'Hospital' },
    School:         { top: 0xffcd50, side: 0xc88c14, name: 'School' },
    Industrial:     { top: 0xb4bec8, side: 0x6e7882, name: 'Industrial' },
    PowerPlant:     { top: 0xc88cff, side: 0x8246c8, name: 'PowerPlant' },
    AmbulanceDepot: { top: 0x5ab4ff, side: 0x286ec8, name: 'AmbulanceDepot' },
    Empty:          { top: 0xa0dca0, side: 0x5a9b5a, name: 'Empty' },
};

// Building heights for each zone type
export const buildingHeights = {
    Residential:    1.2,
    Hospital:       2.8,
    School:         2.2,
    Industrial:     3.0,
    PowerPlant:     3.5,
    AmbulanceDepot: 2.0,
    Empty:          0.0,
};
