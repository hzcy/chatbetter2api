import React, { useEffect, useState } from 'react';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Button,
  Input,
  Pagination,
  Spinner,
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Textarea,
  Switch,
  Progress,
  Badge,
  Tooltip,
  Chip,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
  useDisclosure,
  Select,
  SelectItem,
} from '@nextui-org/react';
import { api } from '../utils/api';
import dayjs from 'dayjs';
import { 
  IoAddOutline, 
  IoSearchOutline, 
  IoCreateOutline, 
  IoTrashOutline, 
  IoRefreshOutline, 
  IoDocumentTextOutline,
  IoEllipsisVerticalOutline,
  IoKeyOutline,
  IoCheckmarkCircleOutline,
  IoAlertCircleOutline,
  IoInformationCircleOutline,
  IoCubeOutline,
  IoRocketOutline
} from 'react-icons/io5';

interface TokenItem {
  id: number;
  account: string;
  token: string;
  silent_cookies: string;
  cookies_expires: string | null;
  auth: string;
  access_token: string;
  token_expires: string | null;
  created_at: string | null;
  updated_at: string | null;
  deleted_at: string | null;
  enable: number;
  count: number;
  account_type: string | null;
}

// 全局Toast通知组件
interface ToastProps {
  type: 'success' | 'error' | 'info';
  message: string;
  isOpen: boolean;
  onClose: () => void;
}

const Toast: React.FC<ToastProps> = ({ type, message, isOpen, onClose }) => {
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => {
        onClose();
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const icons = {
    success: <IoCheckmarkCircleOutline className="text-success" size={24} />,
    error: <IoAlertCircleOutline className="text-danger" size={24} />,
    info: <IoInformationCircleOutline className="text-primary" size={24} />
  };

  const bgColors = {
    success: 'bg-green-50/90 border-green-200/70',
    error: 'bg-rose-50/90 border-rose-200/70',
    info: 'bg-blue-50/90 border-blue-200/70'
  };

  return (
    <div className="fixed top-4 right-4 z-[2000] w-80 animate-fade-in">
      <div className={`${bgColors[type]} p-4 rounded-xl shadow-md backdrop-blur-sm border flex items-start gap-3`}>
        <div className="flex-shrink-0 text-opacity-90">{icons[type]}</div>
        <div className="flex-grow">
          <p className="text-sm text-gray-700">{message}</p>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">×</button>
      </div>
    </div>
  );
};

const TokensPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [tokens, setTokens] = useState<TokenItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [searchQuery, setSearchQuery] = useState('');
  const [windowWidth, setWindowWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1024);
  
  // Add sorting state
  const [sortBy, setSortBy] = useState<string | null>(null);
  const [sortDesc, setSortDesc] = useState(false);

  const [dialogVisible, setDialogVisible] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [currentToken, setCurrentToken] = useState<Partial<TokenItem>>({ enable: 1 });

  const [bulkVisible, setBulkVisible] = useState(false);
  const [bulkData, setBulkData] = useState('');
  const [registrationTask, setRegistrationTask] = useState<string>('');
  const [registrationStatus, setRegistrationStatus] = useState<any>(null);
  const [bulkThreadCount, setBulkThreadCount] = useState(5); // 新增批量注册线程数
  
  // 新增批量刷新状态
  const [batchRefreshVisible, setBatchRefreshVisible] = useState(false);
  const [includeDisabled, setIncludeDisabled] = useState(false);
  const [threadCount, setThreadCount] = useState(5);
  const [batchRefreshTask, setBatchRefreshTask] = useState<string>('');
  const [batchRefreshStatus, setBatchRefreshStatus] = useState<any>(null);

  // 新增刷新模型状态
  const [isRefreshingModels, setIsRefreshingModels] = useState(false);

  // Toast 状态
  const [toast, setToast] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
    isOpen: boolean;
  }>({
    type: 'info',
    message: '',
    isOpen: false,
  });

  const showToast = (type: 'success' | 'error' | 'info', message: string) => {
    setToast({ type, message, isOpen: true });
  };

  const closeToast = () => {
    setToast(prev => ({ ...prev, isOpen: false }));
  };

  const loadTokens = async () => {
    setLoading(true);
    try {
      const res = await api.get('/tokens/', {
        params: {
          skip: (page - 1) * pageSize,
          limit: pageSize,
          ...(searchQuery ? { account: searchQuery } : {}),
          ...(sortBy ? { sort_by: sortBy, sort_desc: sortDesc } : {}),
        },
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
        }
      });
      setTokens(res.data.items);
      setTotal(res.data.total);
    } catch (err) {
      console.error(err);
      showToast('error', '获取Token列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTokens();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, sortBy, sortDesc]);
  
  // Handle column sorting
  const handleSort = (column: string) => {
    if (sortBy === column) {
      // If already sorting by this column, toggle direction
      setSortDesc(!sortDesc);
    } else {
      // Otherwise, sort by this column in ascending order
      setSortBy(column);
      setSortDesc(false);
    }
  };
  
  // Render sort indicator
  const renderSortIndicator = (column: string) => {
    if (sortBy !== column) return null;
    
    return (
      <span className="ml-1 text-blue-500">
        {sortDesc ? " ▼" : " ▲"}
      </span>
    );
  };

  // 监听窗口大小变化
  useEffect(() => {
    const handleResize = () => {
      setWindowWidth(window.innerWidth);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const formatDate = (val: string | null) => (val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-');

  const handleSaveToken = async () => {
    try {
      if (isEditing && currentToken.id) {
        await api.put(`/tokens/${currentToken.id}`, currentToken, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
          }
        });
        showToast('success', '更新成功');
      } else {
        await api.post('/tokens/', currentToken, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
          }
        });
        showToast('success', '添加成功');
      }
      setDialogVisible(false);
      loadTokens();
    } catch (err) {
      showToast('error', '保存失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/tokens/${id}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
        }
      });
      showToast('success', '删除成功');
      loadTokens();
    } catch (err) {
      showToast('error', '删除失败');
    }
  };

  const handleRefreshCookie = async (row: TokenItem) => {
    try {
      await api.post(`/register/refresh/${row.id}`, {}, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
        }
      });
      loadTokens();
      showToast('success', `账号 "${row.account}" 的Cookie刷新成功`);
    } catch (err) {
      showToast('error', '刷新失败');
    }
  };

  // 升级账号
  const handleUpgrade = async (row: TokenItem) => {
    try {
      const res = await api.get(`/tokens/${row.id}/upgrade`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
        }
      });
      const url = res.data.url;
      try {
        await navigator.clipboard.writeText(url);
        showToast('success', '升级链接已复制到剪贴板');
      } catch (copyErr) {
        showToast('info', `复制失败，请手动复制: ${url}`);
      }
    } catch (err) {
      showToast('error', '获取升级链接失败');
    }
  };

  const handleStatusToggle = async (row: TokenItem, val: boolean) => {
    try {
      await api.put(`/tokens/${row.id}`, { enable: val ? 1 : 0 }, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
        }
      });
      // 更新本地状态，使用函数式更新以确保使用最新状态
      setTokens(currentTokens => 
        currentTokens.map(token => 
          token.id === row.id ? { ...token, enable: val ? 1 : 0 } : token
        )
      );
      showToast('success', '状态更新成功');
    } catch (err) {
      // 如果请求失败，需要恢复开关状态
      showToast('error', '状态更新失败');
    }
  };

  /* 批量刷新功能 */
  const startBatchRefresh = async () => {
    try {
      const res = await api.post('/register/batch-refresh', {
        include_disabled: includeDisabled,
        thread_count: threadCount
      }, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
        }
      });
      setBatchRefreshTask(res.data.task_id);
      setBatchRefreshStatus({ status: 'processing', total: res.data.count });
      showToast('info', '批量刷新任务已开始');
    } catch (err) {
      showToast('error', '启动批量刷新失败');
    }
  };

  useEffect(() => {
    if (!batchRefreshTask) return;
    const timer = setInterval(async () => {
      try {
        const res = await api.get(`/register/refresh-status/${batchRefreshTask}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
          }
        });
        setBatchRefreshStatus(res.data);
        if (res.data.status !== 'processing') {
          clearInterval(timer);
          loadTokens();
          showToast('success', `批量刷新完成: 成功${res.data.success}个, 失败${res.data.failed}个`);
        }
      } catch (err) {
        console.error(err);
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [batchRefreshTask]);

  /* 批量解析与注册 */
  const startRegistration = async () => {
    if (!bulkData.trim()) {
      showToast('error', '请输入数据');
      return;
    }
    
    try {
      const res = await api.post('/register/bulk-register', { 
        data: bulkData,
        thread_count: bulkThreadCount 
      }, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
        }
      });
      setRegistrationTask(res.data.task_id);
      setRegistrationStatus({ status: 'processing', total: res.data.count });
      showToast('info', '批量注册任务已开始');
    } catch (err) {
      showToast('error', '启动失败');
    }
  };

  useEffect(() => {
    if (!registrationTask) return;
    const timer = setInterval(async () => {
      try {
        const res = await api.get(`/register/status/${registrationTask}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
          }
        });
        setRegistrationStatus(res.data);
        if (res.data.status !== 'processing') {
          clearInterval(timer);
          loadTokens();
          showToast('success', `批量注册完成: 成功${res.data.success}个, 失败${res.data.failed}个`);
        }
      } catch (err) {
        console.error(err);
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [registrationTask]);

  // 新增刷新模型函数
  const handleRefreshModels = async () => {
    try {
      setIsRefreshingModels(true);
      const res = await api.get('/tokens/refresh-models', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
        }
      });
      
      if (res.data.status === 'success') {
        showToast('success', '模型列表刷新成功');
      } else {
        showToast('error', '模型列表刷新失败，可能因为没有可用的access_token');
      }
    } catch (err) {
      console.error(err);
      showToast('error', '模型数据刷新失败');
    } finally {
      setIsRefreshingModels(false);
    }
  };

  // 显示截断文本
  const renderTruncatedText = (text: string) => {
    return (
      <Tooltip 
        content={
          <div className="max-w-xs break-all whitespace-pre-wrap text-sm p-2">
            {text}
          </div>
        }
        placement="bottom"
        showArrow={true}
        delay={500}
        closeDelay={0}
        classNames={{
          base: "py-2 px-2 shadow-xl",
          content: "break-all whitespace-pre-wrap"
        }}
      >
        <span className="font-mono truncate inline-block max-w-[150px]">
          {text}
        </span>
      </Tooltip>
    );
  };

  // 用于确认删除的弹窗
  const { isOpen: isDeleteConfirmOpen, onOpen: openDeleteConfirm, onClose: closeDeleteConfirm } = useDisclosure();
  const [tokenToDelete, setTokenToDelete] = useState<number | null>(null);

  const confirmDelete = (id: number) => {
    setTokenToDelete(id);
    openDeleteConfirm();
  };

  const executeDelete = async () => {
    if (tokenToDelete !== null) {
      await handleDelete(tokenToDelete);
      closeDeleteConfirm();
    }
  };

  /* 渲染 */
  return (
    <div className="space-y-4">
      {/* 操作栏 */}
      <div className="flex flex-col sm:flex-row flex-wrap items-center gap-2 sm:gap-3 p-3 sm:p-4 bg-gray-50/70 backdrop-blur-sm rounded-xl border border-gray-100/80 shadow-sm mb-4">
        {/* 将原来的flex布局改为grid布局，设置为3列 */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 w-full">
          <Button 
            size="sm" 
            color="secondary" 
            variant="flat"
            startContent={<IoRefreshOutline />}
            className="shadow-sm transition-transform hover:scale-102 active:scale-98 text-base"
            onPress={loadTokens}
          >
            重新加载
          </Button>
          
          <Button 
            size="sm" 
            color="primary" 
            variant="flat"
            startContent={<IoAddOutline />}
            className="shadow-sm transition-transform hover:scale-102 active:scale-98 text-base"
            onPress={() => { setIsEditing(false); setCurrentToken({ enable: 1 }); setDialogVisible(true); }}
          >
            添加 Token
          </Button>
          
          <Button 
            size="sm" 
            color="success" 
            variant="flat"
            startContent={<IoDocumentTextOutline />}
            className="shadow-sm transition-transform hover:scale-102 active:scale-98 text-base"
            onPress={() => setBulkVisible(true)}
          >
            批量注册
          </Button>
          
          <Button 
            size="sm" 
            color="warning" 
            variant="flat"
            startContent={<IoRefreshOutline />}
            className="shadow-sm transition-transform hover:scale-102 active:scale-98 text-base"
            onPress={() => setBatchRefreshVisible(true)}
          >
            批量刷新
          </Button>
          
          {/* 新增刷新模型按钮 */}
          <Button 
            size="sm" 
            color="danger" 
            variant="flat"
            startContent={<IoCubeOutline />}
            className="shadow-sm transition-transform hover:scale-102 active:scale-98 text-base"
            onPress={handleRefreshModels}
            isLoading={isRefreshingModels}
          >
            刷新模型
          </Button>
          
          <Button 
            size="sm"
            color="default"
            variant="flat"
            className="shadow-sm transition-transform hover:scale-102 active:scale-98 text-base"
            startContent={<IoInformationCircleOutline className="text-gray-600" />}
          >
            总数: <span className="font-semibold ml-1">{total}</span>
          </Button>
        </div>
        
        <div className="flex w-full sm:w-auto sm:ml-auto items-center gap-2 mt-4 sm:mt-0">
          <Input
            classNames={{
              base: "flex-1",
              inputWrapper: "h-9 shadow-sm bg-white/80 backdrop-blur-sm",
            }}
            placeholder="搜索账号..."
            size="sm"
            startContent={<IoSearchOutline className="text-gray-400" />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            variant="bordered"
            radius="lg"
          />
          <Button 
            size="sm" 
            className="h-9 shadow-sm transition-transform hover:scale-102 active:scale-98 text-base" 
            color="default" 
            radius="lg"
            onPress={loadTokens}
          >
            搜索
          </Button>
        </div>

        {/* Mobile sort selector */}
        <div className="flex w-full md:hidden mt-2 gap-2 items-center">
          <Select
            label="排序方式"
            size="sm"
            className="flex-1"
            classNames={{
              trigger: "h-9 bg-white/80 backdrop-blur-sm shadow-sm",
            }}
            selectedKeys={sortBy ? [sortBy] : []}
            onChange={(e) => {
              if (e.target.value) {
                setSortBy(e.target.value);
              } else {
                setSortBy(null);
              }
            }}
          >
            <SelectItem key="id" value="id">按ID</SelectItem>
            <SelectItem key="account" value="account">按账号</SelectItem>
            <SelectItem key="created_at" value="created_at">按创建时间</SelectItem>
            <SelectItem key="updated_at" value="updated_at">按更新时间</SelectItem>
            <SelectItem key="count" value="count">按使用次数</SelectItem>
            <SelectItem key="enable" value="enable">按状态</SelectItem>
          </Select>
          {sortBy && (
            <Button
              isIconOnly
              size="sm"
              variant="flat"
              color={sortDesc ? "primary" : "secondary"}
              className="h-9 shadow-sm"
              onClick={() => setSortDesc(!sortDesc)}
            >
              {sortDesc ? "▼" : "▲"}
            </Button>
          )}
        </div>

        {/* Desktop sort indicator */}
        {sortBy && (
          <div className="hidden md:flex w-full sm:w-auto gap-2 mt-2 sm:mt-0 items-center bg-blue-50/80 px-3 py-1.5 rounded-lg">
            <span className="text-xs text-blue-600">
              排序: {
                sortBy === 'id' ? 'ID' :
                sortBy === 'account' ? '账号' :
                sortBy === 'created_at' ? '创建时间' :
                sortBy === 'updated_at' ? '更新时间' :
                sortBy === 'count' ? '次数' : '状态'
              } {sortDesc ? '↓' : '↑'}
            </span>
            <Button
              isIconOnly
              size="sm"
              variant="light"
              className="min-w-0 w-5 h-5 p-0"
              onClick={() => setSortBy(null)}
            >
              ×
            </Button>
          </div>
        )}
      </div>

      {/* 移动端卡片视图 */}
      <div className="block md:hidden">
        {loading ? (
          <div className="flex justify-center items-center py-16">
            <Spinner size="lg" color="primary" labelColor="primary" label="加载中..." />
          </div>
        ) : tokens.length > 0 ? (
          <div className="space-y-3">
            {tokens.map(row => (
              <div key={row.id} className="border rounded-xl shadow-sm p-4 bg-white/90 backdrop-blur-sm transition-all hover:shadow-md hover:bg-white">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <div className="font-medium text-gray-700">{row.account}</div>
                    <div className="text-xs text-gray-400">ID: {row.id}</div>
                  </div>
                  <Dropdown>
                    <DropdownTrigger>
                      <Button isIconOnly size="sm" variant="light" className="rounded-full bg-gray-100/70 hover:bg-gray-200/70">
                        <IoEllipsisVerticalOutline className="text-gray-500" />
                      </Button>
                    </DropdownTrigger>
                    <DropdownMenu aria-label="操作选项">
                      <DropdownItem 
                        key="edit" 
                        startContent={<IoCreateOutline className="text-blue-500" />}
                        onPress={() => { setIsEditing(true); setCurrentToken(row); setDialogVisible(true); }}
                      >
                        编辑
                      </DropdownItem>
                      <DropdownItem 
                        key="refresh" 
                        startContent={<IoRefreshOutline className="text-green-500" />}
                        onPress={() => handleRefreshCookie(row)}
                      >
                        刷新
                      </DropdownItem>
                      <DropdownItem
                        key="upgrade"
                        startContent={<IoRocketOutline className="text-purple-500" />}
                        onPress={() => handleUpgrade(row)}
                      >
                        升级
                      </DropdownItem>
                      <DropdownItem 
                        key="delete" 
                        className="text-danger" 
                        color="danger"
                        startContent={<IoTrashOutline className="text-danger" />}
                        onPress={() => confirmDelete(row.id)}
                      >
                        删除
                      </DropdownItem>
                    </DropdownMenu>
                  </Dropdown>
                </div>

                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="col-span-2 bg-gray-50/80 p-2 rounded-lg">
                    <div className="text-xs font-medium text-gray-500 mb-1">Token:</div>
                    <div className="font-mono text-xs truncate text-gray-600">{row.token}</div>
                  </div>
                  <div className="col-span-2 bg-gray-50/80 p-2 rounded-lg">
                    <div className="text-xs font-medium text-gray-500 mb-1">Silent Cookies:</div>
                    <div className="font-mono text-xs truncate text-gray-600">{row.silent_cookies}</div>
                  </div>
                  <div className="bg-gray-50/80 p-2 rounded-lg">
                    <div className="text-xs font-medium text-gray-500 mb-1">账号类型:</div>
                    <Chip 
                      color={row.account_type === 'free' ? 'default' : row.account_type === 'pro' ? 'success' : 'primary'} 
                      size="sm" 
                      variant="flat"
                    >
                      {row.account_type || '-'}
                    </Chip>
                  </div>
                  <div className="bg-gray-50/80 p-2 rounded-lg">
                    <div className="text-xs font-medium text-gray-500 mb-1">创建时间:</div>
                    <div className="text-xs text-gray-600">{formatDate(row.created_at)}</div>
                  </div>
                  <div className="bg-gray-50/80 p-2 rounded-lg">
                    <div className="text-xs font-medium text-gray-500 mb-1">更新时间:</div>
                    <div className="text-xs text-gray-600">{formatDate(row.updated_at)}</div>
                  </div>
                  <div className="flex items-center bg-gray-50/80 p-2 rounded-lg">
                    <div className="text-xs font-medium text-gray-500 mr-2">次数:</div>
                    <Chip color="primary" size="sm" variant="flat" className="text-sm bg-blue-100/50">
                      {row.count}
                    </Chip>
                  </div>
                  <div className="flex items-center bg-gray-50/80 p-2 rounded-lg">
                    <div className="text-xs font-medium text-gray-500 mr-2">状态:</div>
                    <Switch
                      size="sm"
                      color="success"
                      isSelected={row.enable === 1}
                      onValueChange={(val) => handleStatusToggle(row, val)}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-12 text-center border rounded-xl shadow-sm bg-white/80">
            <IoKeyOutline size={40} className="mx-auto text-gray-300/70 mb-3" />
            <p className="text-gray-500 text-sm">暂无数据</p>
          </div>
        )}
      </div>

      {/* 桌面端表格视图 */}
      <div className="hidden md:block">
        {loading ? (
          <div className="flex justify-center items-center py-16">
            <Spinner size="lg" color="primary" labelColor="primary" label="加载中..." />
          </div>
        ) : (
          <div className="border rounded-xl shadow-sm overflow-hidden bg-white/90 backdrop-blur-sm w-full">
            <div className="overflow-x-auto">
              <Table 
                aria-label="Token Table" 
                classNames={{
                  th: "bg-gray-50/80 text-gray-600 font-medium text-sm",
                  td: "py-3 px-3 text-sm text-gray-600 border-b border-gray-100/60",
                  table: "min-w-full w-full",
                }}
                selectionMode="none"
                removeWrapper
              >
                <TableHeader>
                  <TableColumn 
                    width={60} 
                    onClick={() => handleSort('id')}
                    className="cursor-pointer hover:bg-gray-100"
                  >
                    ID{renderSortIndicator('id')}
                  </TableColumn>
                  <TableColumn 
                    width={200}
                    onClick={() => handleSort('account')}
                    className="cursor-pointer hover:bg-gray-100"
                  >
                    账号{renderSortIndicator('account')}
                  </TableColumn>
                  <TableColumn width={300}>Token</TableColumn>
                  <TableColumn width={300}>Silent Cookies</TableColumn>
                  <TableColumn 
                    width={120}
                    onClick={() => handleSort('account_type')}
                    className="cursor-pointer hover:bg-gray-100"
                  >
                    账号类型{renderSortIndicator('account_type')}
                  </TableColumn>
                  <TableColumn 
                    width={200}
                    onClick={() => handleSort('created_at')}
                    className="cursor-pointer hover:bg-gray-100"
                  >
                    创建时间{renderSortIndicator('created_at')}
                  </TableColumn>
                  <TableColumn 
                    width={200}
                    onClick={() => handleSort('updated_at')}
                    className="cursor-pointer hover:bg-gray-100"
                  >
                    更新时间{renderSortIndicator('updated_at')}
                  </TableColumn>
                  <TableColumn 
                    width={100}
                    onClick={() => handleSort('count')}
                    className="cursor-pointer hover:bg-gray-100"
                  >
                    次数{renderSortIndicator('count')}
                  </TableColumn>
                  <TableColumn 
                    width={100}
                    onClick={() => handleSort('enable')}
                    className="cursor-pointer hover:bg-gray-100"
                  >
                    状态{renderSortIndicator('enable')}
                  </TableColumn>
                  <TableColumn width={100}>操作</TableColumn>
                </TableHeader>
                <TableBody items={tokens} emptyContent={
                  <div className="py-8 text-center">
                    <IoKeyOutline size={36} className="mx-auto text-gray-300 mb-2" />
                    <p className="text-gray-500 text-sm">暂无数据</p>
                  </div>
                }>
                  {(row: TokenItem) => (
                    <TableRow key={row.id} className="hover:bg-gray-50">
                      <TableCell>{row.id}</TableCell>
                      <TableCell>
                        <div className="font-medium">{row.account}</div>
                      </TableCell>
                      <TableCell>{renderTruncatedText(row.token)}</TableCell>
                      <TableCell>{renderTruncatedText(row.silent_cookies)}</TableCell>
                      <TableCell>
                        <Chip 
                          color={row.account_type === 'free' ? 'default' : row.account_type === 'pro' ? 'success' : 'primary'} 
                          size="sm" 
                          variant="flat"
                        >
                          {row.account_type || '-'}
                        </Chip>
                      </TableCell>
                      <TableCell>{formatDate(row.created_at)}</TableCell>
                      <TableCell>{formatDate(row.updated_at)}</TableCell>
                      <TableCell>
                        <Chip color="primary" size="sm" variant="flat" className="text-sm">
                          {row.count}
                        </Chip>
                      </TableCell>
                      <TableCell>
                        <Switch
                          size="sm"
                          color="success"
                          isSelected={row.enable === 1}
                          onValueChange={(val) => handleStatusToggle(row, val)}
                        />
                      </TableCell>
                      <TableCell>
                        <Dropdown>
                          <DropdownTrigger>
                            <Button isIconOnly size="sm" variant="light">
                              <IoEllipsisVerticalOutline />
                            </Button>
                          </DropdownTrigger>
                          <DropdownMenu aria-label="操作选项">
                            <DropdownItem 
                              key="edit" 
                              startContent={<IoCreateOutline className="text-blue-500" />}
                              onPress={() => { setIsEditing(true); setCurrentToken(row); setDialogVisible(true); }}
                            >
                              编辑
                            </DropdownItem>
                            <DropdownItem 
                              key="refresh" 
                              startContent={<IoRefreshOutline className="text-green-500" />}
                              onPress={() => handleRefreshCookie(row)}
                            >
                              刷新
                            </DropdownItem>
                            <DropdownItem 
                              key="upgrade" 
                              startContent={<IoRocketOutline className="text-purple-500" />}
                              onPress={() => handleUpgrade(row)}
                            >
                              升级
                            </DropdownItem>
                            <DropdownItem 
                              key="delete" 
                              className="text-danger" 
                              color="danger"
                              startContent={<IoTrashOutline className="text-danger" />}
                              onPress={() => confirmDelete(row.id)}
                            >
                              删除
                            </DropdownItem>
                          </DropdownMenu>
                        </Dropdown>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
      </div>

      {/* 分页 */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 mt-4">
        <div className="flex flex-wrap items-center gap-2 sm:gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xs sm:text-sm text-gray-600">每页显示:</span>
            <Select
              size="sm"
              variant="bordered"
              className="w-16 sm:w-20 min-w-unit-16 bg-white/80 backdrop-blur-sm shadow-sm"
              defaultSelectedKeys={[pageSize.toString()]}
              onChange={(e) => {
                if (e.target.value) {
                  setPageSize(Number(e.target.value));
                  setPage(1); // 重置到第一页
                }
              }}
              radius="lg"
              classNames={{
                trigger: "shadow-sm border-gray-200/80 bg-white/80",
              }}
            >
              <SelectItem key="15" value="15">15</SelectItem>
              <SelectItem key="20" value="20">20</SelectItem>
              <SelectItem key="30" value="30">30</SelectItem>
              <SelectItem key="50" value="50">50</SelectItem>
              <SelectItem key="100" value="100">100</SelectItem>
            </Select>
          </div>
          <span className="text-xs sm:text-sm text-gray-600">
            共 <span className="font-medium text-gray-700">{total}</span> 条数据
          </span>
        </div>
        
        <Pagination 
          total={Math.ceil(total / pageSize)} 
          page={page} 
          onChange={setPage} 
          showControls
          variant="bordered"
          classNames={{
            cursor: "bg-blue-500/90",
            item: "bg-white/80 backdrop-blur-sm transition-all hover:bg-gray-100/80",
            wrapper: "shadow-sm"
          }}
          className="mx-auto sm:mx-0"
          radius="full"
        />
      </div>

      {/* 添加/编辑弹窗 */}
      <Modal 
        isOpen={dialogVisible} 
        onOpenChange={setDialogVisible} 
        backdrop="blur" 
        size={windowWidth < 768 ? "full" : "xl"}
        placement="center" 
        scrollBehavior="inside"
        className="md:max-w-3xl"
        classNames={{
          backdrop: "bg-gradient-to-b from-gray-900/40 to-gray-900/60",
          base: "bg-white/90 dark:bg-gray-900/90 backdrop-blur-md border border-gray-200/50 dark:border-gray-700/50",
          header: "border-b border-gray-200/50 dark:border-gray-700/50",
          footer: "border-t border-gray-200/50 dark:border-gray-700/50",
          closeButton: "hover:bg-gray-200/30 active:bg-gray-200/50"
        }}
      >
        <ModalContent>
          {(onClose) => (
            <>
              <ModalHeader className="flex flex-col gap-1">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-full bg-blue-100/50 text-blue-600">
                    {isEditing ? <IoCreateOutline size={18} /> : <IoAddOutline size={18} />}
                  </div>
                  <span className="font-semibold text-gray-700">{isEditing ? '编辑 Token' : '添加 Token'}</span>
                </div>
              </ModalHeader>
              <ModalBody className="gap-5 py-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Input
                    label="账号"
                    value={currentToken.account ?? ''}
                    onChange={(e) => setCurrentToken({ ...currentToken, account: e.target.value })}
                    variant="bordered"
                    radius="lg"
                    classNames={{
                      label: "text-gray-600",
                      inputWrapper: "bg-white/80 backdrop-blur-sm"
                    }}
                  />
                  <div className="md:col-span-2">
                    <Textarea
                      label="Token"
                      value={currentToken.token ?? ''}
                      onChange={(e) => setCurrentToken({ ...currentToken, token: e.target.value })}
                      variant="bordered"
                      radius="lg"
                      minRows={2}
                      classNames={{
                        label: "text-gray-600",
                        inputWrapper: "bg-white/80 backdrop-blur-sm"
                      }}
                    />
                  </div>
                  <div className="md:col-span-2">
                    <Textarea
                      label="Silent Cookies"
                      value={currentToken.silent_cookies ?? ''}
                      onChange={(e) => setCurrentToken({ ...currentToken, silent_cookies: e.target.value })}
                      variant="bordered"
                      radius="lg"
                      minRows={2}
                      classNames={{
                        label: "text-gray-600",
                        inputWrapper: "bg-white/80 backdrop-blur-sm"
                      }}
                    />
                  </div>
                  <div className="md:col-span-2">
                    <Textarea
                      label="Auth"
                      value={currentToken.auth ?? ''}
                      onChange={(e) => setCurrentToken({ ...currentToken, auth: e.target.value })}
                      variant="bordered"
                      radius="lg"
                      minRows={2}
                      classNames={{
                        label: "text-gray-600",
                        inputWrapper: "bg-white/80 backdrop-blur-sm"
                      }}
                    />
                  </div>
                  <div className="md:col-span-2">
                    <Input
                      label="账号类型"
                      value={currentToken.account_type ?? ''}
                      onChange={(e) => setCurrentToken({ ...currentToken, account_type: e.target.value })}
                      variant="bordered"
                      radius="lg"
                      classNames={{
                        label: "text-gray-600",
                        inputWrapper: "bg-white/80 backdrop-blur-sm"
                      }}
                    />
                  </div>
                  <div className="md:col-span-2">
                    <Textarea
                      label="Access Token"
                      value={currentToken.access_token ?? ''}
                      onChange={(e) => setCurrentToken({ ...currentToken, access_token: e.target.value })}
                      variant="bordered"
                      radius="lg"
                      minRows={2}
                      classNames={{
                        label: "text-gray-600",
                        inputWrapper: "bg-white/80 backdrop-blur-sm"
                      }}
                    />
                  </div>
                  <div className="flex items-center">
                    <Switch
                      isSelected={currentToken.enable === 1}
                      onValueChange={(val) => setCurrentToken({ ...currentToken, enable: val ? 1 : 0 })}
                      size="sm"
                      color="success"
                    >
                      <span className="ml-2 text-gray-600">启用</span>
                    </Switch>
                  </div>
                </div>
              </ModalBody>
              <ModalFooter className="border-t px-6 py-3">
                <Button 
                  variant="light" 
                  onPress={onClose}
                  radius="lg"
                  className="shadow-sm transition-all hover:bg-gray-100/80"
                >
                  取消
                </Button>
                <Button 
                  color="primary" 
                  onPress={handleSaveToken}
                  radius="lg"
                  className="shadow-sm transition-all"
                >
                  保存
                </Button>
              </ModalFooter>
            </>
          )}
        </ModalContent>
      </Modal>

      {/* 删除确认弹窗 */}
      <Modal 
        isOpen={isDeleteConfirmOpen} 
        onOpenChange={closeDeleteConfirm} 
        size="sm"
        classNames={{
          backdrop: "bg-gradient-to-b from-gray-900/40 to-gray-900/60",
          base: "bg-white/90 dark:bg-gray-900/90 backdrop-blur-md border border-gray-200/50 dark:border-gray-700/50",
          header: "border-b border-gray-200/50 dark:border-gray-700/50",
          footer: "border-t border-gray-200/50 dark:border-gray-700/50",
          closeButton: "hover:bg-gray-200/30 active:bg-gray-200/50"
        }}
      >
        <ModalContent>
          {(onClose) => (
            <>
              <ModalHeader className="flex items-center gap-2">
                <div className="p-2 rounded-full bg-red-100/50">
                  <IoTrashOutline className="text-red-500" size={18} />
                </div>
                <span className="font-semibold text-gray-700">确认删除</span>
              </ModalHeader>
              <ModalBody>
                <p className="text-gray-600">确定要删除该 Token 吗？此操作无法撤销。</p>
              </ModalBody>
              <ModalFooter>
                <Button 
                  variant="light" 
                  onPress={onClose}
                  radius="lg"
                  className="shadow-sm transition-all hover:bg-gray-100/80"
                >
                  取消
                </Button>
                <Button 
                  color="danger" 
                  onPress={executeDelete}
                  radius="lg"
                  className="shadow-sm transition-all"
                >
                  删除
                </Button>
              </ModalFooter>
            </>
          )}
        </ModalContent>
      </Modal>

      {/* Bulk 注册弹窗 */}
      <Modal 
        isOpen={bulkVisible} 
        onOpenChange={setBulkVisible} 
        size={windowWidth < 768 ? "full" : "2xl"}
        backdrop="blur"
        scrollBehavior="inside"
        className="md:max-w-4xl"
        classNames={{
          backdrop: "bg-gradient-to-b from-gray-900/40 to-gray-900/60",
          base: "bg-white/90 dark:bg-gray-900/90 backdrop-blur-md border border-gray-200/50 dark:border-gray-700/50",
          header: "border-b border-gray-200/50 dark:border-gray-700/50",
          footer: "border-t border-gray-200/50 dark:border-gray-700/50",
          closeButton: "hover:bg-gray-200/30 active:bg-gray-200/50"
        }}
      >
        <ModalContent>
          {(onClose) => (
            <>
              <ModalHeader className="flex items-center gap-3">
                <div className="p-2 rounded-full bg-green-100/50">
                  <IoDocumentTextOutline className="text-green-600" size={18} />
                </div>
                <span className="font-semibold text-gray-700">批量注册</span>
              </ModalHeader>
              <ModalBody className="py-5">
                {registrationStatus ? (
                  <div className="w-full space-y-6">
                    <Progress 
                      value={(registrationStatus.processed / registrationStatus.total) * 100} 
                      color="success"
                      showValueLabel
                      size="md"
                      classNames={{
                        base: "max-w-md mx-auto",
                        label: "text-sm font-medium",
                        value: "text-sm font-medium",
                        track: "rounded-full bg-green-100/30",
                        indicator: "rounded-full bg-green-500/80"
                      }}
                      label="处理进度"
                      valueLabel={`${Math.round((registrationStatus.processed / registrationStatus.total) * 100)}%`}
                    />
                    <div className="bg-gray-50/70 backdrop-blur-sm rounded-xl p-5 border border-gray-100/80 shadow-sm">
                      <div className="grid grid-cols-2 gap-4 text-center">
                        <div>
                          <div className="text-xs text-gray-500 mb-1">总数</div>
                          <div className="text-lg font-semibold text-gray-700">{registrationStatus.total}</div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 mb-1">已处理</div>
                          <div className="text-lg font-semibold text-gray-700">{registrationStatus.processed}</div>
                        </div>
                        <div>
                          <div className="text-xs text-green-500 mb-1">成功</div>
                          <div className="text-lg font-semibold text-green-600/90">{registrationStatus.success}</div>
                        </div>
                        <div>
                          <div className="text-xs text-red-500 mb-1">失败</div>
                          <div className="text-lg font-semibold text-red-500/80">{registrationStatus.failed}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="text-sm text-gray-600 mb-3">每行一条数据，格式为：outlook Email----Password----RefreshToken----Client_ID</p>
                    <Textarea
                      rows={10}
                      placeholder="outlook Email----Password----RefreshToken----Client_ID 每行一条"
                      value={bulkData}
                      onChange={(e) => setBulkData(e.target.value)}
                      variant="bordered"
                      radius="lg"
                      disableAutosize={false}
                      minRows={8}
                      maxRows={20}
                      classNames={{
                        input: "resize-y min-h-[180px]",
                        inputWrapper: "bg-white/80 backdrop-blur-sm"
                      }}
                    />
                    
                    {/* 添加线程数输入 */}
                    <div className="mt-4">
                      <Input
                        label="线程数"
                        type="number"
                        value={bulkThreadCount.toString()}
                        onChange={(e) => setBulkThreadCount(parseInt(e.target.value) || 1)}
                        min={1}
                        max={20}
                        variant="bordered"
                        radius="lg"
                        classNames={{
                          label: "text-gray-600 text-sm",
                          inputWrapper: "bg-white/80 backdrop-blur-sm"
                        }}
                        description="并发注册的线程数（1-20）"
                      />
                    </div>
                  </>
                )}
              </ModalBody>
              <ModalFooter className="border-t px-6 py-3">
                {!registrationStatus && (
                  <>
                    <Button 
                      color="success" 
                      onPress={startRegistration}
                      radius="lg"
                      className="shadow-sm transition-all ml-auto"
                    >
                      开始注册
                    </Button>
                  </>
                )}
                {registrationStatus && registrationStatus.status !== 'processing' && (
                  <Button 
                    color="primary" 
                    onPress={() => { setRegistrationTask(''); setRegistrationStatus(null); onClose(); }}
                    radius="lg"
                    className="shadow-sm transition-all"
                  >
                    完成
                  </Button>
                )}
              </ModalFooter>
            </>
          )}
        </ModalContent>
      </Modal>

      {/* 批量刷新弹窗 */}
      <Modal 
        isOpen={batchRefreshVisible} 
        onOpenChange={setBatchRefreshVisible} 
        size={windowWidth < 768 ? "full" : "md"}
        backdrop="blur"
        scrollBehavior="inside"
        className="md:max-w-md"
        classNames={{
          backdrop: "bg-gradient-to-b from-gray-900/40 to-gray-900/60",
          base: "bg-white/90 dark:bg-gray-900/90 backdrop-blur-md border border-gray-200/50 dark:border-gray-700/50",
          header: "border-b border-gray-200/50 dark:border-gray-700/50",
          footer: "border-t border-gray-200/50 dark:border-gray-700/50",
          closeButton: "hover:bg-gray-200/30 active:bg-gray-200/50"
        }}
      >
        <ModalContent>
          {(onClose) => (
            <>
              <ModalHeader className="flex items-center gap-3">
                <div className="p-2 rounded-full bg-amber-100/50">
                  <IoRefreshOutline className="text-amber-600" size={18} />
                </div>
                <span className="font-semibold text-gray-700">批量刷新</span>
              </ModalHeader>
              <ModalBody className="py-5">
                {batchRefreshStatus ? (
                  <div className="w-full space-y-6">
                    <Progress 
                      value={(batchRefreshStatus.processed / batchRefreshStatus.total) * 100} 
                      color="warning"
                      showValueLabel
                      size="md"
                      classNames={{
                        base: "max-w-md mx-auto",
                        label: "text-sm font-medium",
                        value: "text-sm font-medium",
                        track: "rounded-full bg-amber-100/30",
                        indicator: "rounded-full bg-amber-500/80"
                      }}
                      label="处理进度"
                      valueLabel={`${Math.round((batchRefreshStatus.processed / batchRefreshStatus.total) * 100)}%`}
                    />
                    <div className="bg-gray-50/70 backdrop-blur-sm rounded-xl p-5 border border-gray-100/80 shadow-sm">
                      <div className="grid grid-cols-2 gap-4 text-center">
                        <div>
                          <div className="text-xs text-gray-500 mb-1">总数</div>
                          <div className="text-lg font-semibold text-gray-700">{batchRefreshStatus.total}</div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 mb-1">已处理</div>
                          <div className="text-lg font-semibold text-gray-700">{batchRefreshStatus.processed}</div>
                        </div>
                        <div>
                          <div className="text-xs text-green-500 mb-1">成功</div>
                          <div className="text-lg font-semibold text-green-600/90">{batchRefreshStatus.success}</div>
                        </div>
                        <div>
                          <div className="text-xs text-red-500 mb-1">失败</div>
                          <div className="text-lg font-semibold text-red-500/80">{batchRefreshStatus.failed}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="text-sm text-gray-600 mb-4">选择批量刷新选项：</p>
                    <div className="space-y-4">
                      <div className="flex items-center">
                        <Switch 
                          isSelected={includeDisabled}
                          onValueChange={setIncludeDisabled}
                          size="sm"
                          color="warning"
                        >
                          <span className="ml-2 text-sm">包含已失效的账号</span>
                        </Switch>
                      </div>
                      <Input
                        label="线程数"
                        type="number"
                        value={threadCount.toString()}
                        onChange={(e) => setThreadCount(parseInt(e.target.value) || 1)}
                        min={1}
                        max={20}
                        variant="bordered"
                        radius="lg"
                        classNames={{
                          label: "text-gray-600 text-sm",
                          inputWrapper: "bg-white/80 backdrop-blur-sm"
                        }}
                        description="并发刷新的线程数（1-20）"
                      />
                    </div>
                  </>
                )}
              </ModalBody>
              <ModalFooter className="border-t px-6 py-3">
                {!batchRefreshStatus && (
                  <>
                    <Button 
                      color="warning" 
                      onPress={startBatchRefresh}
                      radius="lg"
                      className="shadow-sm transition-all ml-auto"
                    >
                      开始刷新
                    </Button>
                  </>
                )}
                {batchRefreshStatus && batchRefreshStatus.status !== 'processing' && (
                  <Button 
                    color="primary" 
                    onPress={() => { setBatchRefreshTask(''); setBatchRefreshStatus(null); onClose(); }}
                    radius="lg"
                    className="shadow-sm transition-all"
                  >
                    完成
                  </Button>
                )}
              </ModalFooter>
            </>
          )}
        </ModalContent>
      </Modal>

      {/* Toast通知 */}
      <Toast
        type={toast.type}
        message={toast.message}
        isOpen={toast.isOpen}
        onClose={closeToast}
      />
    </div>
  );
};

export default TokensPage; 