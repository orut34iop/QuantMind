import { AccountInfo } from '../services/realTradingService';

/**
 * 投资组合通用工具函数
 */

export type StockNameMap = Record<string, string>;
export type RawPosition = Record<string, unknown>;

export const toFiniteNumber = (value: unknown, fallback = 0): number => {
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
};

export const toPositiveNumber = (value: unknown, fallback = NaN): number => {
    const num = Number(value);
    return Number.isFinite(num) && num > 0 ? num : fallback;
};

/**
 * 归一化持仓数据结构（适配不同后端和券商格式）
 */
export const normalizePositions = (accountInfo: AccountInfo | null): Array<{ key: string | null; pos: RawPosition }> => {
    const raw = (accountInfo as any)?.positions;
    if (Array.isArray(raw)) {
        return raw
            .filter((item): item is RawPosition => !!item && typeof item === 'object')
            .map((pos) => ({ key: null, pos }));
    }
    if (raw && typeof raw === 'object') {
        return Object.entries(raw as Record<string, unknown>)
            .filter(([, value]) => !!value && typeof value === 'object')
            .map(([key, value]) => ({ key, pos: value as RawPosition }));
    }
    return [];
};

/**
 * 解析股票代码
 */
export const resolveCode = (entryKey: string | null, pos: RawPosition): string => {
    const key = String(entryKey || '').trim();
    const candidates = [
        pos.symbol,
        pos.stock_code,
        pos.code,
        pos.ts_code,
        key,
    ];
    for (const candidate of candidates) {
        const text = String(candidate || '').trim();
        if (!text) continue;
        if (text === '0' && String(pos.symbol || '').trim()) continue;
        return text;
    }
    return key || '--';
};

/**
 * 解析股票名称
 */
export const resolveName = (code: string, pos: RawPosition, stockNames: StockNameMap): string => {
    const mapped = String(stockNames[code] || '').trim();
    if (mapped) return mapped;
    const inlineName = String(pos.name || pos.stock_name || pos.symbol_name || '').trim();
    return inlineName || code;
};

/**
 * 动态计算当前持仓的投资胜率
 * 定义：(盈利持仓数 / 总持仓数) * 100
 */
export interface WinRateResult {
    winRate: number;
    total: number;
    winning: number;
}

export const calculatePositionsWinRate = (accountInfo: AccountInfo | null): WinRateResult => {
    const normalized = normalizePositions(accountInfo);
    if (normalized.length === 0) {
        return { winRate: 0, total: 0, winning: 0 };
    }

    let winningCount = 0;
    let validCount = 0;

    normalized.forEach(({ pos }) => {
        const shares = toFiniteNumber(pos.volume ?? pos.qty ?? pos.quantity ?? pos.total_volume, 0);
        if (shares <= 0) return; // 忽略空仓或无效仓位
        
        // 优先使用明确的盈亏字段判定胜负（针对已持久化或后端计算好的快照）
        const floatPnl = toFiniteNumber(pos.float_pnl ?? pos.unrealized_pnl ?? pos.pnl ?? pos.profit ?? (pos as any).today_pnl, Number.NaN);
        
        if (Number.isFinite(floatPnl)) {
            if (floatPnl > 0) {
                winningCount++;
            }
            validCount++;
        } else {
            // 兜底逻辑：手动计算当前持仓盈亏状态
            const price = toPositiveNumber(pos.last_price ?? pos.current_price ?? pos.price, 0);
            const cost = toPositiveNumber(pos.cost_price ?? pos.avg_cost ?? pos.avg_price ?? pos.cost, 0);

            if (price > 0 && cost > 0) {
                validCount++;
                if (price > cost) {
                    winningCount++;
                }
            }
        }
    });

    if (validCount === 0) {
        return { winRate: 0, total: 0, winning: 0 };
    }

    return {
        winRate: (winningCount / validCount) * 100,
        total: validCount,
        winning: winningCount
    };
};
