import React, { useState } from 'react';
import { Card, Input, Button } from '@nextui-org/react';
import { IoKeyOutline, IoLogInOutline } from 'react-icons/io5';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const LoginPage: React.FC = () => {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleLogin = async () => {
    if (!password.trim()) {
      setError('请输入密码');
      return;
    }
    
    setError('');
    setLoading(true);
    try {
      // 只在请求头中发送密码，请求体为空
      const response = await axios.post('/api/tokens/login', 
        {}, // 空请求体
        {
          headers: {
            'Authorization': `Bearer ${password}`
          }
        }
      );
      
      // 登录成功，将密码本身存储到localStorage
      localStorage.setItem('adminToken', password);
      navigate('/tokens');
    } catch (err: any) {
      setError(err.response?.data?.detail ?? '登录失败，请检查密码');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleLogin();
    }
  };

  return (
    <div className="flex h-screen justify-center items-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="w-full max-w-md px-4">
        <Card className="w-full px-6 py-8 shadow-xl border border-blue-50">
          <div className="flex flex-col items-center mb-8">
            <div className="p-3 bg-blue-100 rounded-full mb-4">
              <IoKeyOutline size={32} className="text-blue-600" />
            </div>
            <h2 className="text-2xl font-semibold text-gray-800">
              ChatBetter2API
            </h2>
            <p className="text-gray-500 mt-1">管理员登录</p>
          </div>
          
          <div className="space-y-6">
            <Input
              type="password"
              placeholder="请输入管理员密码"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyPress={handleKeyPress}
              startContent={<IoKeyOutline className="text-gray-400" />}
              variant="bordered"
              color={error ? "danger" : "default"}
              isInvalid={!!error}
              errorMessage={error}
              classNames={{
                input: "pl-1",
                inputWrapper: "h-11",
              }}
            />
            
            <Button 
              color="primary" 
              className="w-full h-11 font-medium"
              startContent={!loading && <IoLogInOutline size={18} />}
              onPress={handleLogin} 
              isLoading={loading}
              disableAnimation={loading}
              disableRipple={loading}
              radius="sm"
            >
              {loading ? "登录中..." : "登录"}
            </Button>
            
            <div className="text-center text-xs text-gray-400 mt-4">
              © {new Date().getFullYear()} ChatBetter2API Admin
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default LoginPage; 