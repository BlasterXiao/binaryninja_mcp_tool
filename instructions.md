# Binary ninja mcp server

## 需求分析文档

- 使用 Gemini 先对需求进行分析，并生成需求分析文档

``` gemini pro 深度研究
检索所有关于 binary ninja 反编译工具的相关资料和api文档，主要目的是想做一个针对 bianry ninja 的mcp服务器，可以提供给我的cursor调用，前提是我的 binary ninja 是 pro版本，不支持无头模式。
```

- 通过开发指南获取一个需求分析文档

``` cursor sonnet4.6
通过 C:\Users\32669\Desktop\rust\rust第一课\w5\001-bn-mcp-server-开发指南.md 生成一份需求文档，最终的协议采用 http 协议，不是 sse 协议。功能上要完整，支持各类的关于 binary ninja 的功能。最终将需求文档写入 C:\Users\32669\Desktop\rust\rust第一课\w5\002-bn-mcp-server-需求文档.md 文件中。

```

## 开发计划

通过 C:\Users\32669\Desktop\rust\rust第一课\w5\002-bn-mcp-server-需求文档.md 生成一份开发计划，最终将开发计划写入 C:\Users\32669\Desktop\rust\rust第一课\w5\003-bn-mcp-server-开发计划.md 文件中。实现功能和计划中要多增加一些 merge 图，架构图、流程图等信息，可以只管的看到整个的开发过程。

## 实现开发计划

根据 @003-bn-mcp-server-开发计划.md  完成里面的所以实现开发计划。
