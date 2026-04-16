import React from 'react';

interface CommunityPaginationProps {
  currentPage: number;
  totalPages: number;
  pages: number[];
  onPageChange: (page: number) => void;
}

export const CommunityPagination: React.FC<CommunityPaginationProps> = ({ currentPage, totalPages, pages, onPageChange }) => {
  if (totalPages <= 1) {
    return null;
  }

  return (
    <div className="page-controls container">
      <div className="pagination" aria-label="分页导航">
        <button type="button" className="page-btn" onClick={() => onPageChange(currentPage - 1)} disabled={currentPage === 1}>
          上一页
        </button>
        {pages.map(page => (
          <button
            key={page}
            type="button"
            className={`page-btn ${page === currentPage ? 'active' : ''}`}
            onClick={() => onPageChange(page)}
          >
            {page}
          </button>
        ))}
        <button
          type="button"
          className="page-btn"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
        >
          下一页
        </button>
      </div>
    </div>
  );
};
