import React, { useState, useEffect } from 'react';
import {Navbar, NavbarBrand, NavbarContent, NavbarItem, Button, Tooltip} from '@nextui-org/react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { IoKeyOutline, IoLogOutOutline, IoMenuOutline, IoHomeOutline } from 'react-icons/io5';

interface Props {
  children: React.ReactNode;
}

const AdminLayout: React.FC<Props> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // 检测窗口大小，自动设置侧边栏状态
  useEffect(() => {
    const checkIfMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    
    // 初始检查
    checkIfMobile();
    
    // 窗口大小变化时检查
    window.addEventListener('resize', checkIfMobile);
    
    // 在移动设备上自动折叠侧边栏
    if (isMobile && !collapsed) {
      setCollapsed(true);
    }
    
    return () => window.removeEventListener('resize', checkIfMobile);
  }, [isMobile]);

  const handleLogout = () => {
    localStorage.removeItem('adminToken');
    navigate('/login');
  };

  const toggleSidebar = () => {
    setCollapsed(!collapsed);
  };

  const menuItems = [
    { path: '/tokens', label: 'Token 管理', icon: <IoKeyOutline size={20} /> },
    // 可以在这里添加更多菜单项
  ];

  return (
    <div className="flex h-screen bg-gray-50">
      {/* 侧边栏背景遮罩 - 移动端菜单打开时显示 */}
      {!collapsed && isMobile && (
        <div 
          className="fixed inset-0 bg-black/50 z-30 md:hidden" 
          onClick={toggleSidebar}
        />
      )}
      
      {/* 侧边栏 */}
      <div 
        className={`fixed md:static z-40 h-full transition-all duration-300 ease-in-out 
          ${collapsed ? (isMobile ? 'w-0 -translate-x-full' : 'w-14') : (isMobile ? 'w-48' : 'w-52')} 
          bg-gradient-to-b from-blue-900 to-indigo-800 text-white shadow-lg`}
      >
        <div className="flex items-center justify-between p-3 border-b border-blue-700">
          {!collapsed && <div className="font-bold text-base">管理菜单</div>}
          <Button 
            isIconOnly 
            variant="light" 
            className="text-white ml-auto" 
            onPress={toggleSidebar}
          >
            <IoMenuOutline size={20} />
          </Button>
        </div>
        
        {/* 只在非移动设备或移动设备但菜单展开时显示 */}
        {(!isMobile || (isMobile && !collapsed)) && (
          <div className="py-4">
            {menuItems.map((item) => (
              <Tooltip
                key={item.path}
                content={collapsed ? item.label : ""}
                placement="right"
                showArrow
                classNames={{
                  base: "py-2 px-4 shadow-xl text-sm"
                }}
                isDisabled={!collapsed || isMobile}
              >
                <Link 
                  to={item.path} 
                  className={`flex items-center px-4 py-3 ${location.pathname === item.path 
                    ? 'bg-blue-700 text-white' 
                    : 'text-blue-100 hover:bg-blue-700/50'} transition-colors duration-200 ${
                      collapsed && !isMobile ? 'justify-center' : 'space-x-3'
                    }`}
                  onClick={isMobile ? toggleSidebar : undefined}
                >
                  <div className="flex-shrink-0">{item.icon}</div>
                  {(!collapsed || isMobile) && <span>{item.label}</span>}
                </Link>
              </Tooltip>
            ))}
          </div>
        )}
      </div>
      
      {/* 主内容区域 */}
      <div className="flex-1 flex flex-col overflow-hidden w-full">
        <Navbar 
          className="border-b shadow-sm bg-white" 
          maxWidth="full"
        >
          <NavbarContent className="gap-4">
            <Button
              isIconOnly
              variant="light"
              className="md:hidden"
              onPress={toggleSidebar}
            >
              <IoMenuOutline size={20} />
            </Button>
            <NavbarBrand>
              <div className="flex items-center gap-2">
                <IoHomeOutline size={20} className="text-blue-600" />
                <span className="font-bold text-blue-600 text-sm sm:text-base">ChatBetter2API 管理系统</span>
              </div>
            </NavbarBrand>
          </NavbarContent>
          <NavbarContent justify="end">
            <NavbarItem>
              <Button 
                color="danger" 
                variant="light" 
                onPress={handleLogout} 
                startContent={<IoLogOutOutline size={18} />}
                className="font-medium"
                size="md"
              >
                <span className="hidden md:inline">退出登录</span>
              </Button>
            </NavbarItem>
          </NavbarContent>
        </Navbar>
        <div className="p-2 sm:p-4 md:p-6 overflow-y-auto flex-1 bg-gray-50">
          <div className="w-full bg-white rounded-lg shadow-sm p-2 sm:p-4 md:p-6">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminLayout; 