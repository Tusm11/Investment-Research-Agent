/**
 * Frontend Metric Formatters
 * Handle conversion of API data to display-ready strings
 * All formatters return 'N/A' for missing/invalid data
 */

/**
 * Format market cap: ₹1234L Cr, ₹123K Cr, ₹1.2B, etc.
 */
function formatMarketCap(value) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  
  const v = parseFloat(value);
  if (v === 0) return '₹0';
  
  // Crore base: 1 Cr = 1e7
  const inCrore = v / 1e7;
  
  if (inCrore >= 100000) return `₹${(inCrore / 100000).toFixed(1)}B`;  // Billion (10000 Cr)
  if (inCrore >= 1000) return `₹${(inCrore / 1000).toFixed(1)}K Cr`;   // Thousand Cr
  if (inCrore >= 1) return `₹${inCrore.toFixed(1)}L Cr`;               // Lakh Cr
  
  // Below 1 Cr - show in rupees
  return `₹${v.toFixed(0)}`;
}

/**
 * Format P/E, P/B, and other ratios: 25.4x, N/A
 */
function formatRatio(value, decimals = 1) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  
  const v = parseFloat(value);
  return v === 0 ? 'N/A' : `${v.toFixed(decimals)}x`;
}

/**
 * Format percentage: 15.5%, N/A
 */
function formatPercentage(value, decimals = 1) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  
  const v = parseFloat(value);
  return `${v.toFixed(decimals)}%`;
}

/**
 * Format currency: ₹1,234.50, ₹1.2K, N/A
 */
function formatCurrency(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  
  const v = parseFloat(value);
  if (v === 0) return '₹0';
  if (v >= 1000) return `₹${(v / 1000).toFixed(1)}K`;
  
  return `₹${v.toFixed(decimals)}`;
}

/**
 * Format EPS: 25.4, N/A
 */
function formatEPS(value, decimals = 1) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  
  const v = parseFloat(value);
  return v === 0 ? 'N/A' : `${v.toFixed(decimals)}`;
}

/**
 * Format Dividend Yield with % symbol
 */
function formatDividendYield(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  
  const v = parseFloat(value);
  return `${v.toFixed(decimals)}%`;
}

/**
 * Format ROE, ROA, Margin percentages
 */
function formatMargin(value, decimals = 1) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  
  const v = parseFloat(value);
  return `${v.toFixed(decimals)}%`;
}

/**
 * Format large counts: 1.2K, 1.5M, N/A
 */
function formatCount(value) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  
  const v = parseFloat(value);
  if (v >= 1000000) return `${(v / 1000000).toFixed(1)}M`;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}K`;
  return `${v.toFixed(0)}`;
}

/**
 * Format volume in crores
 */
function formatVolume(value) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  
  const v = parseFloat(value);
  const inCrore = v / 1e7;
  if (inCrore >= 1) return `${inCrore.toFixed(1)} Cr`;
  return `₹${v.toFixed(0)}`;
}

/**
 * Format debt: ₹1.2B, ₹123K, ₹1234 Cr, N/A
 */
function formatDebt(value) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  
  const v = parseFloat(value);
  const inCrore = v / 1e7;
  
  if (inCrore >= 10000) return `₹${(inCrore / 10000).toFixed(1)}B`;
  if (inCrore >= 1) return `₹${inCrore.toFixed(0)} Cr`;
  return `₹${v.toFixed(0)}`;
}

/**
 * Format generic number with optional unit
 */
function formatNumber(value, unit = '', decimals = 1) {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  
  const v = parseFloat(value);
  return `${v.toFixed(decimals)}${unit ? ' ' + unit : ''}`;
}
