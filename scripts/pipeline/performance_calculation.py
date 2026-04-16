#!/usr/bin/env python3
"""
单台16核32GB服务器性能预估
基于 QuantMind 实际压测数据
"""

# ========== 已知性能数据 ==========
SINGLE_INSTANCE_QPS = 127  # 单实例QPS (来自压测报告)
AVG_RESPONSE_TIME = 150  # 平均响应时间 ms
API_WORKERS = 4  # 每个服务的worker数

# ========== 服务器配置 ==========
TOTAL_CORES = 16
TOTAL_MEMORY_GB = 32

# ========== 服务配置 ==========
services = {
    "PostgreSQL": {"cores": 4, "memory": 8, "qps_capacity": 500},
    "Redis": {"cores": 2, "memory": 4, "qps_capacity": 10000},
    "API Gateway": {"cores": 2, "memory": 4, "workers": 4},
    "User Service": {"cores": 2, "memory": 4, "workers": 4},
    "Trading Service": {"cores": 2, "memory": 4, "workers": 4},
    "Market Data": {"cores": 2, "memory": 4, "workers": 2},
    "Nginx": {"cores": 0.5, "memory": 0.5, "qps_capacity": 5000},
    "Monitoring": {"cores": 1, "memory": 2},
    "System": {"cores": 0.5, "memory": 1.5},
}

# ========== 计算总资源 ==========
total_cores_used = sum(s["cores"] for s in services.values())
total_memory_used = sum(s["memory"] for s in services.values())

print("=" * 60)
print("🖥️  单台16核32GB服务器性能预估")
print("=" * 60)

print("\n📊 资源分配:")
for name, config in services.items():
    print(f"  {name:20s}: {config['cores']:4.1f}核  {config['memory']:5.1f}GB")

print(f"\n  {'总计':20s}: {total_cores_used:4.1f}核  {total_memory_used:5.1f}GB")
print(
    f"  {'利用率':20s}: {total_cores_used/TOTAL_CORES*100:4.1f}%   {total_memory_used/TOTAL_MEMORY_GB*100:5.1f}%"
)

# ========== QPS计算 ==========
print("\n" + "=" * 60)
print("⚡ 并发处理能力分析")
print("=" * 60)

# 每个服务的QPS = 单worker QPS × worker数量
api_gateway_qps = SINGLE_INSTANCE_QPS * 4
user_service_qps = SINGLE_INSTANCE_QPS * 4
trading_service_qps = SINGLE_INSTANCE_QPS * 4
market_data_qps = SINGLE_INSTANCE_QPS * 2

total_qps = min(
    api_gateway_qps,  # 入口限制
    services["PostgreSQL"]["qps_capacity"],  # 数据库限制
    services["Redis"]["qps_capacity"],  # 缓存限制
)

print("\n各服务QPS能力:")
print(f"  API Gateway:     {api_gateway_qps} QPS (瓶颈: 入口)")
print(f"  User Service:    {user_service_qps} QPS")
print(f"  Trading Service: {trading_service_qps} QPS")
print(f"  Market Data:     {market_data_qps} QPS")
print(
    f"  PostgreSQL:      {services['PostgreSQL']['qps_capacity']} QPS (瓶颈: 数据库)")
print(f"  Redis:           {services['Redis']['qps_capacity']} QPS")
print(f"  Nginx:           {services['Nginx']['qps_capacity']} QPS")

print(f"\n系统总QPS: {api_gateway_qps} (受API Gateway限制)")

# ========== 用户数计算 ==========
print("\n" + "=" * 60)
print("👥 并发用户数预估")
print("=" * 60)

# 假设场景
requests_per_user_per_minute = 10  # 每用户每分钟请求数
qps_per_user = requests_per_user_per_minute / 60

concurrent_users_normal = int(api_gateway_qps / qps_per_user)
concurrent_users_peak = int(api_gateway_qps / qps_per_user * 0.7)  # 考虑70%峰值

print(f"\n假设: 每用户每分钟{requests_per_user_per_minute}次请求")
print(f"  常规负载: {concurrent_users_normal} 并发用户")
print(f"  峰值负载: {concurrent_users_peak} 并发用户 (70%容量)")

# ========== 不同场景分析 ==========
print("\n" + "=" * 60)
print("📈 不同使用场景分析")
print("=" * 60)

scenarios = [
    {"name": "轻度使用", "req_per_min": 5, "users": 300},
    {"name": "中度使用", "req_per_min": 10, "users": 200},
    {"name": "重度使用", "req_per_min": 20, "users": 100},
]

for scenario in scenarios:
    req_per_min = scenario["req_per_min"]
    users = scenario["users"]
    total_qps_needed = users * req_per_min / 60
    utilization = (total_qps_needed / api_gateway_qps) * 100

    status = "✅" if utilization < 70 else "⚠️" if utilization < 90 else "❌"

    print(f"\n{scenario['name']} (每用户{req_per_min}次/分钟):")
    print(f"  {users}用户 = {total_qps_needed:.1f} QPS")
    print(f"  负载率: {utilization:.1f}% {status}")

# ========== 扩展建议 ==========
print("\n" + "=" * 60)
print("🚀 扩展建议")
print("=" * 60)

print("""
当前配置适用于:
  ✅ 0-200 并发用户 (中度使用)
  ✅ 0-300 并发用户 (轻度使用)

需要扩展的信号:
  ⚠️  CPU使用率持续 > 80%
  ⚠️  内存使用率持续 > 85%
  ⚠️  API响应时间 > 500ms
  ⚠️  数据库连接数 > 80

扩展路径:
  1️⃣  升级到 32核64GB (支持500-800用户)
  2️⃣  拆分为 2台服务器 (应用+数据库分离)
  3️⃣  采用原完整架构 (支持1000+用户)
""")

print("=" * 60)
