import React, { useState } from 'react';
import { Card, AutoComplete, Button, List, Typography, Space, message, Spin, Input, Empty } from 'antd';
import { PlusOutlined, DeleteOutlined, SearchOutlined, StockOutlined } from '@ant-design/icons';
import { useWizardStore } from '../store/wizardStore';
import { searchStocks } from '../services/wizardService';
import { debounce } from 'lodash';

const { Text } = Typography;

export const CustomStockSelector: React.FC = () => {
  const { customPool, addCustomStock, removeCustomStock } = useWizardStore();
  const [options, setOptions] = useState<{ value: string; label: React.ReactNode; stock: any }[]>([]);
  const [searchValue, setSearchValue] = useState('');
  const [searching, setSearching] = useState(false);

  // Debounce search to avoid too many requests
  const handleSearch = async (value: string) => {
    setSearchValue(value);
    if (!value) {
      setOptions([]);
      return;
    }
    setSearching(true);
    try {
      const results = await searchStocks(value);
      setOptions(results.map((r: any) => ({
        value: r.symbol,
        label: (
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>{r.name} ({r.symbol})</span>
            <span style={{ color: '#fa541c' }}>{r.price}</span>
          </div>
        ),
        stock: r
      })));
    } catch (e) {
      // ignore
    } finally {
      setSearching(false);
    }
  };

  const handleSelect = (value: string, option: any) => {
    addCustomStock(option.stock);
    setSearchValue('');
    setOptions([]);
    message.success(`已添加 ${option.stock.name}`);
  };

  return (
    <Card
      title={<Space><StockOutlined /><span>自定义选股池</span></Space>}
      size="small"
      variant="borderless"
      style={{ background: '#fafafa', height: '100%', display: 'flex', flexDirection: 'column' }}
      styles={{ body: { flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' } }}
    >
      <div style={{ marginBottom: 12 }}>
        <AutoComplete
          value={searchValue}
          options={options}
          style={{ width: '100%' }}
          onSearch={handleSearch}
          onSelect={handleSelect}
          placeholder="输入代码/简称搜索 (如: 000001)"
        >
           <Input
             suffix={searching ? <Spin size="small" /> : <SearchOutlined style={{ color: '#bfbfbf' }} />}
             allowClear
           />
        </AutoComplete>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', border: '1px solid #f0f0f0', borderRadius: 4, background: '#fff' }}>
        <List
          size="small"
          dataSource={customPool || []}
          locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无自选" /> }}
          renderItem={(item) => (
            <List.Item
              actions={[<Button type="text" danger icon={<DeleteOutlined />} size="small" onClick={() => removeCustomStock(item.symbol)} />]}
              style={{ padding: '8px 12px' }}
            >
               <div style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
                 <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Text strong>{item.name}</Text>
                    {item.price && <Text type="success" style={{ color: '#cf1322' }}>{item.price}</Text>}
                 </div>
                 <Text type="secondary" style={{ fontSize: 11 }}>{item.symbol}</Text>
               </div>
            </List.Item>
          )}
        />
      </div>
      <div style={{ marginTop: 8, textAlign: 'right' }}>
         <Text type="secondary" style={{ fontSize: 12 }}>已选 {customPool?.length || 0} 只</Text>
      </div>
    </Card>
  );
};
