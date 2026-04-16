export const FACTOR_DICTIONARY_VERSION = '1.0.0';

export const FACTORS: Array<{ key: string; label: string; category: string }> = [
  { key: 'market_cap', label: '总市值(亿)', category: 'valuation' },
  { key: 'pe', label: '市盈率PE', category: 'valuation' },
  { key: 'pb', label: '市净率PB', category: 'valuation' },
];

export const SYNONYMS: Record<string, string> = {
  市值: 'market_cap',
  总市值: 'market_cap',
  市值亿: 'market_cap',
  PE: 'pe',
  PE_TTM: 'pe',
  市盈率: 'pe',
  PB: 'pb',
  市净率: 'pb',
};
