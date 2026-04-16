import React, { useEffect, useState } from 'react';
import { Table, Button, Space, message, Tag, Popconfirm } from 'antd';
import { adminService } from '../services/adminService';
import { CommunityPost } from '../types';

export const AdminCommunityAudit: React.FC = () => {
    const [posts, setPosts] = useState<CommunityPost[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);

    useEffect(() => {
        loadPosts();
    }, []);

    const loadPosts = async (page = 1) => {
        setLoading(true);
        try {
            const data = await adminService.listPosts(page);
            setPosts(data.items);
            setTotal(data.total);
        } catch (err) {
            message.error('加载社区动态失败');
        } finally {
            setLoading(false);
        }
    };

    const handleModerate = async (postId: number, field: 'pinned' | 'featured', value: boolean) => {
        try {
            await adminService.moderatePost(postId, { [field]: value });
            message.success('治理操作成功');
            loadPosts();
        } catch (err) {
            message.error('操作失败');
        }
    };

    const handleDelete = async (postId: number) => {
        try {
            await adminService.deletePost(postId);
            message.success('帖子已下架');
            loadPosts();
        } catch (err) {
            message.error('物理删除失败');
        }
    };

    const columns = [
        {
            title: '标题/内容',
            dataIndex: 'title',
            key: 'title',
            render: (text: string, record: CommunityPost) => (
                <div>
                    <div className="font-bold text-slate-800">{text}</div>
                    <div className="text-[10px] text-slate-400 mt-1">
                        Author: {record.author_id} · {new Date(record.created_at).toLocaleDateString()}
                    </div>
                </div>
            )
        },
        {
            title: '分类',
            dataIndex: 'category',
            key: 'category',
            render: (cat: string) => <Tag className="text-[10px] uppercase font-black">{cat}</Tag>
        },
        {
            title: '互动',
            key: 'stats',
            render: (_: any, record: CommunityPost) => (
                <span className="text-xs text-slate-500">
                    👁️ {record.views} · ❤️ {record.likes} · 💬 {record.comments}
                </span>
            )
        },
        {
            title: '标记',
            key: 'flags',
            render: (_: any, record: CommunityPost) => (
                <Space>
                    {record.pinned && <Tag color="rose" className="text-[10px] font-black">PINNED</Tag>}
                    {record.featured && <Tag color="blue" className="text-[10px] font-black">FEATURED</Tag>}
                </Space>
            )
        },
        {
            title: '操作',
            key: 'action',
            align: 'right' as const,
            render: (_: any, record: CommunityPost) => (
                <Space size="small">
                    <Button
                        size="small"
                        type="link"
                        onClick={() => handleModerate(record.id, 'pinned', !record.pinned)}
                    >
                        {record.pinned ? '取消置顶' : '置顶'}
                    </Button>
                    <Button
                        size="small"
                        type="link"
                        onClick={() => handleModerate(record.id, 'featured', !record.featured)}
                    >
                        {record.featured ? '取消精选' : '精选'}
                    </Button>
                    <Popconfirm title="确定物理删除此内容且不可恢复吗？" onConfirm={() => handleDelete(record.id)}>
                        <Button size="small" type="link" danger>删除</Button>
                    </Popconfirm>
                </Space>
            ),
        },
    ];

    return (
        <div className="space-y-4">
            <h3 className="text-lg font-bold text-slate-800 mb-6">社区治理</h3>
            <Table
                columns={columns}
                dataSource={posts}
                rowKey="id"
                loading={loading}
                pagination={{
                    total,
                    pageSize: 20,
                    onChange: (page) => loadPosts(page)
                }}
                className="border border-slate-100 rounded-xl overflow-hidden shadow-sm"
            />
        </div>
    );
};
