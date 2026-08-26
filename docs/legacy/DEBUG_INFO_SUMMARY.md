# Debug信息添加总结

本文档总结了在ZhouTomo项目中添加的所有debug信息，用于帮助定位相机参数设置时出现500错误的问题。

## 已添加Debug信息的位置

### 1. 服务器端 (server_fastapi.py)

#### 1.1 set_component_params函数
- 添加了详细的参数验证日志
- 记录显微镜连接状态
- 记录组件存在性检查
- 记录参数类型和内容
- 记录完整的异常堆栈跟踪

#### 1.2 get_microscope_aggregate函数
- 记录wiring对象状态
- 记录连接状态检查
- 记录aggregate对象获取过程
- 记录完整的异常堆栈跟踪

#### 1.3 get_microscope_wiring函数
- 记录server_state对象状态
- 记录microscope_wiring对象状态
- 记录对象类型信息

#### 1.4 ServerState.is_microscope_connected方法
- 记录microscope_wiring对象状态
- 记录连接状态检查过程
- 记录异常信息

#### 1.5 set_microscope_wiring函数
- 记录传入的wiring对象信息
- 记录设置过程
- 记录设置后的状态

### 2. 装配层 (wiring.py)

#### 2.1 MicroscopeWiring.set_component_params方法
- 记录组件和参数信息
- 记录aggregate对象状态
- 记录参数设置结果
- 记录完整的异常堆栈跟踪

#### 2.2 MicroscopeWiring.connect方法
- 记录工厂创建过程
- 记录显微镜实例创建
- 记录聚合根创建
- 记录完整的异常堆栈跟踪

#### 2.3 MicroscopeWiring.is_connected方法
- 记录microscope和aggregate对象状态
- 记录连接状态检查过程
- 记录异常信息

#### 2.4 MicroscopeWiring._create_factory方法
- 记录模式选择过程
- 记录工厂创建过程
- 记录异常信息

#### 2.5 LocalTemscriptFactory.create_microscope方法
- 记录temscript模块导入
- 记录仪器实例获取
- 记录连接验证过程
- 记录显微镜实例创建
- 记录完整的异常堆栈跟踪

#### 2.6 NullMicroscopeFactory.create_microscope方法
- 记录NullMicroscope导入
- 记录模拟器实例创建
- 记录完整的异常堆栈跟踪

### 3. 领域层 (domain.py)

#### 3.1 MicroscopeAggregate.set_component_params方法
- 记录组件和参数信息
- 记录可用组件列表
- 记录microscope对象状态
- 记录参数设置结果
- 记录完整的异常堆栈跟踪

### 4. 硬件接口层 (ports_temscript.py)

#### 4.1 TemscriptMicroscope.set_component_params方法
- 记录组件和参数信息
- 记录可用组件列表
- 记录组件映射
- 记录Port对象状态
- 记录参数设置结果
- 记录完整的异常堆栈跟踪

#### 4.2 TemscriptMicroscope.__init__方法
- 记录instrument参数信息
- 记录所有组件端口初始化过程
- 记录完整的异常堆栈跟踪

#### 4.3 CameraPortTS.set_params方法
- 记录参数信息
- 记录cameras对象状态
- 记录camera对象状态
- 记录camera_params对象状态
- 记录参数设置过程
- 记录完整的异常堆栈跟踪

#### 4.4 NullMicroscope.set_component_params方法
- 记录组件和参数信息
- 记录可用组件列表
- 记录组件映射
- 记录Port对象状态
- 记录参数设置结果
- 记录完整的异常堆栈跟踪

#### 4.5 NullPort.set_params方法
- 记录参数信息
- 记录模拟器模式状态

#### 4.6 BasePort.__init__方法
- 记录instrument参数信息
- 记录instrument设置过程
- 记录验证过程

#### 4.7 BasePort._validate_instrument方法
- 记录instrument对象状态
- 记录Configuration访问过程
- 记录异常信息

#### 4.8 create_temscript_microscope函数
- 记录instrument参数信息
- 记录TemscriptMicroscope创建过程
- 记录完整的异常堆栈跟踪

#### 4.9 validate_temscript_connection函数
- 记录instrument参数信息
- 记录Configuration访问过程
- 记录验证结果

### 5. 启动入口 (run_agent.py)

#### 5.1 AgentManager.initialize方法
- 记录配置信息
- 记录显微镜装配创建过程
- 记录连接过程
- 记录服务器状态创建
- 记录完整的异常堆栈跟踪

#### 5.2 AgentManager._connect_microscope方法
- 记录wiring对象状态
- 记录连接过程
- 记录连接验证
- 记录显微镜信息获取
- 记录完整的异常堆栈跟踪

#### 5.3 main函数
- 记录microscope wiring设置过程
- 记录服务器启动过程
- 记录配置信息

## Debug信息的作用

这些debug信息将帮助我们：

1. **追踪请求流程**：从HTTP请求到最终的参数设置，每个步骤都有详细日志
2. **定位异常位置**：记录每个函数调用的开始和结束，以及异常发生的具体位置
3. **检查对象状态**：记录关键对象的状态、类型和内容
4. **验证参数传递**：记录参数在各个层级之间的传递过程
5. **检查连接状态**：记录显微镜连接和验证的每个步骤
6. **获取完整堆栈**：在异常发生时提供完整的调用堆栈信息

## 使用方法

1. 重新启动服务器，观察启动日志
2. 运行example_agent_client_usage.py中的相机参数设置部分
3. 查看服务器日志，找到500错误的具体原因
4. 根据日志信息定位问题所在

## 预期问题类型

基于代码分析，可能的问题包括：

1. **temscript模块导入失败**：本地模式时temscript不可用
2. **仪器连接失败**：无法获取有效的temscript.Instrument实例
3. **组件初始化失败**：某个Port对象创建失败
4. **参数类型不匹配**：传入的参数与期望的类型不符
5. **temscript API调用失败**：访问camera.AcqParams等属性时出错

通过详细的debug信息，我们应该能够准确定位问题所在。

