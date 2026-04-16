import React from 'react';
import { Empty } from 'antd';
import { Settings2 } from 'lucide-react';

interface OtherSettingsProps {
  userId: string;
  tenantId: string;
}

export const OtherSettings: React.FC<OtherSettingsProps> = ({ userId: _userId, tenantId: _tenantId }) => {
  return (
    <div className="w-full pt-1">
      <div className="w-full rounded-xl border border-dashed border-gray-200 bg-white min-h-[280px] flex items-center justify-center">
        <Empty
          image={<Settings2 size={28} className="text-gray-300" />}
          description="其他设置暂未开放"
        />
      </div>
    </div>
  );
};

export default OtherSettings;
