/**
 * Qlib 策略模板类型定义 + 轻量离线 Fallback
 *
 * 主数据源：后端 GET /api/v1/strategies/templates（动态加载）
 * 本文件中的 QLIB_STRATEGY_TEMPLATES 仅作离线 / 后端不可用时的兜底展示。
 * 如需动态获取最新模板，请使用 strategyTemplateService.getTemplates()。
 */

export interface StrategyTemplate {
  id: string;
  name: string;
  description: string;
  category: 'basic' | 'advanced' | 'risk_control';
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  code: string;
  params: {
    name: string;
    description: string;
    default: number | string;
    min?: number;
    max?: number;
  }[];
  execution_defaults?: Record<string, unknown>;
  live_defaults?: Record<string, unknown>;
  live_config_tips?: string[];
}

/**
 * 轻量离线 fallback（仅保留最常用的 3 个入门策略）。
 * 完整模板列表由后端动态提供，优先通过 strategyTemplateService.getTemplates() 获取。
 */
export const QLIB_STRATEGY_TEMPLATES: StrategyTemplate[] = [
  {
    id: 'standard_topk',
    name: '默认 Top-K 选股策略',
    description: '最经典的量化选股逻辑。每日截面排名，精选最具潜力的 Top-K 标的，等权持仓。',
    category: 'basic',
    difficulty: 'beginner',
    code: `"""
默认 Top-K 选股策略 (Standard Top-K Strategy)
[Native] 核心逻辑：Top-K 选股 + 零换手强制约束
"""
STRATEGY_CONFIG = {
    "class": "RedisTopkStrategy",
    "kwargs": {
        "signal": "<PRED>",
        "topk": 50,
        "n_drop": 10,
    }
}
`,
    params: [
      { name: 'topk', description: '持仓股票总数', default: 50, min: 5, max: 100 }
    ]
  },
  {
    id: 'StopLoss',
    name: '止损止盈策略',
    description: '在标准 TopK 选股基础上叠加硬性止损/止盈规则，一旦触发立即强制平仓。',
    category: 'risk_control',
    difficulty: 'beginner',
    code: `"""
止损止盈策略 (Stop-Loss / Take-Profit Strategy)
[Native] 核心逻辑：浮亏超过 stop_loss 或浮盈超过 take_profit 时强制平仓。
"""
STRATEGY_CONFIG = {
    "class": "RedisStopLossStrategy",
    "kwargs": {
        "signal": "<PRED>",
        "topk": 30,
        "n_drop": 6,
        "stop_loss": -0.08,
        "take_profit": 0.15,
    }
}
`,
    params: [
      { name: 'topk', description: '选股数量', default: 30, min: 5, max: 100 },
      { name: 'stop_loss', description: '止损阈值 (如 -0.08 = -8%)', default: -0.08, min: -0.3, max: -0.01 },
      { name: 'take_profit', description: '止盈阈值 (如 0.15 = +15%)', default: 0.15, min: 0.05, max: 0.5 }
    ]
  },
  {
    id: 'alpha_cross_section',
    name: '截面 Alpha 预测策略',
    description: '根据预测分自动分配资金权重，分高者重仓。',
    category: 'advanced',
    difficulty: 'intermediate',
    code: `"""
截面 Alpha 预测策略 (Cross-sectional Alpha)
[Native] 核心逻辑：按模型预测分比例进行权重分配。
"""
STRATEGY_CONFIG = {
    "class": "RedisWeightStrategy",
    "kwargs": {
        "signal": "<PRED>",
        "topk": 50,
        "min_score": 0.0,
        "max_weight": 0.05,
    }
}
`,
    params: [
      { name: 'topk', description: '参与权重的标的数量', default: 50, min: 10, max: 200 },
      { name: 'max_weight', description: '单票持仓上限 (0~1)', default: 0.05, min: 0.01, max: 0.2 }
    ]
  }
];

/**
 * 按分类获取 fallback 模板
 */
export function getTemplatesByCategory(category: StrategyTemplate['category']): StrategyTemplate[] {
  return QLIB_STRATEGY_TEMPLATES.filter(t => t.category === category);
}

/**
 * 按难度获取 fallback 模板
 */
export function getTemplatesByDifficulty(difficulty: StrategyTemplate['difficulty']): StrategyTemplate[] {
  return QLIB_STRATEGY_TEMPLATES.filter(t => t.difficulty === difficulty);
}

/**
 * 按 ID 查询 fallback 模板
 */
export function getTemplateById(id: string): StrategyTemplate | undefined {
  return QLIB_STRATEGY_TEMPLATES.find(t => t.id === id);
}
