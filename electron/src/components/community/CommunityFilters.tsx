import React from 'react';
import type { CommunitySort } from './types';

interface CommunityFiltersProps {
  options: CommunitySort[];
  activeSort: CommunitySort;
  searchTerm: string;
  onSortChange: (value: CommunitySort) => void;
  onSearchChange: (value: string) => void;
}

import { Search } from 'lucide-react';

export const CommunityFilters: React.FC<CommunityFiltersProps> = ({
  options,
  activeSort,
  searchTerm,
  onSortChange,
  onSearchChange,
}) => {
  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    onSearchChange(event.target.value);
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-2 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-1">
        {options.map(option => (
          <button
            key={option}
            type="button"
            className={`px-5 py-2 rounded-xl text-sm font-bold transition-all ${
              activeSort === option
                ? 'bg-slate-900 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-600 hover:bg-slate-50'
            }`}
            onClick={() => onSortChange(option)}
          >
            {option}
          </button>
        ))}
      </div>

      <div className="relative w-72">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          id="communitySearch"
          type="search"
          placeholder="搜索动态、用户或策略…"
          value={searchTerm}
          onChange={handleSearchChange}
          className="w-full pl-10 pr-4 py-2 bg-slate-50 border-none rounded-xl text-sm font-medium focus:ring-4 focus:ring-blue-500/10 focus:bg-white transition-all outline-none"
        />
      </div>
    </div>
  );
};
