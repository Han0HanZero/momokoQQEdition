# 桃桃子QQ版

[![IIIA-3](https://img.shields.io/badge/IIIA-3-A865B3)](https://github.com/ErSanSan233/IIIA)

## 概述

这是一个十分简陋和脆弱的QQ机器人，存在的唯一目的就是供我练习写代码。

* 本仓库的代码均为手动上传，不使用Git进行管理；
* 作为一个练习用仓库，本仓库婉拒任何PR，敬请见谅。
* 代码中的烈度计算公式为我使用国家地震科学数据中心的部分仪器烈度数据自行拟合所得，暂名为HanZero's CSIS Intensity Estimation Model (HCIEM) v1；
* 代码编写中有大语言模型参与。过半数思路由LLM提供，约一至二成代码由LLM提供；
* 本仓库用MIT License开源；© HanZero。

## 功能特性

* 通过WebSocket连接Wolfx Open API的中国地震台网 地震预警 JSON API，收到EEW推送时逐单聊和群聊计算预估本地烈度，如果对方/有成员预估本地烈度超过阈值，发出预警；
* 监听所有聊天，对以斜杠开头的消息作出反应，将其分发给通过装饰器注册好的模块化命令处理器并取得响应。

## 现有命令处理器

* help.py：包含1个命令，用来发送帮助文本；
* register.py：包含1个命令，允许用户将自己或自己所在的群聊注册进机器人的聊天列表，或将自己注册进自己所在的群聊的成员列表。

## 使用方法

1. 在QQ开放平台注册一个机器人，将获得的App ID和Secret填入config.json
2. 启动main.py
3. 执行`/register help`（单聊）或`@\[机器人] /register help`查看注册帮助
4. 注册
5. 使用

## 需求

* Python 3.11

## 鸣谢

* [Wolfx Open API](https://wolfx.jp/apidoc_zh)
* [DeepSeek](https://chat.deepseek.com)

