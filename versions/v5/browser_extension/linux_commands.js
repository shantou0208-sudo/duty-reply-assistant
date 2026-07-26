globalThis.DUTY_LINUX_COMMANDS = [
  {
    category: "Slurm",
    title: "查看节点状态",
    command: "sinfo -N -l",
    description: "逐节点查看分区、状态、CPU 数量和时间限制。",
    keywords: "怎么看节点 查看节点 node 节点状态 partition 分区"
  },
  {
    category: "Slurm",
    title: "查看分区概况",
    command: "sinfo",
    description: "查看所有分区及节点的空闲、占用、维护等状态。",
    keywords: "队列 分区 partition idle alloc down"
  },
  {
    category: "Slurm",
    title: "查看自己的作业",
    command: "squeue -u $USER",
    description: "列出当前用户正在排队和运行的作业。",
    keywords: "查看作业 任务 排队 running pending job"
  },
  {
    category: "Slurm",
    title: "查看作业详细信息",
    command: "scontrol show job <JOBID>",
    description: "查看指定作业的资源、节点、状态和 Pending 原因。",
    keywords: "作业详情 为什么排队 pending reason jobid"
  },
  {
    category: "Slurm",
    title: "查看节点详细信息",
    command: "scontrol show node <NODE>",
    description: "查看指定节点的 CPU、内存、GPU 和当前状态。",
    keywords: "节点详情 内存 GPU gres node"
  },
  {
    category: "Slurm",
    title: "查看历史作业与资源消耗",
    command: "sacct -j <JOBID> --format=JobID,State,Elapsed,AllocCPUS,MaxRSS,ExitCode",
    description: "查看历史作业状态、运行时间、最大内存和退出码。",
    keywords: "历史作业 内存消耗 maxrss elapsed exitcode"
  },
  {
    category: "Slurm",
    title: "取消作业",
    command: "scancel <JOBID>",
    description: "取消指定 Slurm 作业。",
    keywords: "停止作业 删除任务 cancel kill job"
  },
  {
    category: "Slurm",
    title: "提交作业脚本",
    command: "sbatch job.slurm",
    description: "将批处理脚本提交给 Slurm。",
    keywords: "提交任务 脚本 submit job"
  },
  {
    category: "Slurm",
    title: "申请交互式资源",
    command: "salloc -p <PARTITION> -N 1 --gres=gpu:1",
    description: "申请一个节点和一张 GPU 的交互式资源。",
    keywords: "交互节点 申请资源 gpu salloc partition"
  },
  {
    category: "GPU",
    title: "查看 GPU 状态",
    command: "nvidia-smi",
    description: "查看 GPU 型号、显存、利用率和正在使用 GPU 的进程。",
    keywords: "显卡 显存 GPU利用率 cuda process"
  },
  {
    category: "GPU",
    title: "持续观察 GPU",
    command: "watch -n 1 nvidia-smi",
    description: "每秒刷新一次 GPU 状态。",
    keywords: "实时监控 GPU 刷新 显存"
  },
  {
    category: "GPU",
    title: "查看可见 GPU 编号",
    command: "echo $CUDA_VISIBLE_DEVICES",
    description: "查看当前作业被分配后可见的 GPU 编号。",
    keywords: "cuda visible devices 查看分配显卡"
  },
  {
    category: "文件",
    title: "查看当前目录文件",
    command: "ls -lah",
    description: "显示隐藏文件，并用易读单位显示文件大小。",
    keywords: "列出文件 看文件 list hidden size"
  },
  {
    category: "文件",
    title: "查看当前目录总大小",
    command: "du -sh .",
    description: "统计当前目录占用的总空间。",
    keywords: "文件夹大小 目录大小 disk usage"
  },
  {
    category: "文件",
    title: "查看各子目录大小",
    command: "du -h --max-depth=1 | sort -h",
    description: "统计当前目录下各一级文件或目录的大小并排序。",
    keywords: "哪个文件夹大 子目录 排序 size"
  },
  {
    category: "文件",
    title: "查看磁盘剩余空间",
    command: "df -h",
    description: "显示各文件系统容量、已用和剩余空间。",
    keywords: "磁盘空间 剩余容量 filesystem"
  },
  {
    category: "文件",
    title: "按名称查找文件",
    command: "find . -type f -name '*关键词*'",
    description: "从当前目录递归查找文件名包含关键词的文件。",
    keywords: "找文件 搜索文件 filename locate"
  },
  {
    category: "文件",
    title: "查找大文件",
    command: "find . -type f -size +1G -exec ls -lh {} \\;",
    description: "查找当前目录中大于 1 GiB 的文件。",
    keywords: "大文件 占空间 1G size"
  },
  {
    category: "文本",
    title: "在文件中搜索关键词",
    command: "grep -Rni '关键词' .",
    description: "递归搜索当前目录文件内容，并显示文件名和行号。",
    keywords: "查内容 搜文本 grep keyword line"
  },
  {
    category: "文本",
    title: "查看文件末尾",
    command: "tail -n 50 <FILE>",
    description: "查看文件最后 50 行。",
    keywords: "最后几行 末尾 output log"
  },
  {
    category: "文本",
    title: "实时查看输出文件",
    command: "tail -f <FILE>",
    description: "持续显示文件新追加的内容，适合观察日志。",
    keywords: "实时日志 输出变化 log follow"
  },
  {
    category: "文本",
    title: "分页查看文本",
    command: "less <FILE>",
    description: "分页浏览大文件，按 / 搜索，按 q 退出。",
    keywords: "打开大文件 分页 搜索 less"
  },
  {
    category: "文本",
    title: "统计行数",
    command: "wc -l <FILE>",
    description: "统计文本文件的行数。",
    keywords: "多少行 count lines"
  },
  {
    category: "文本",
    title: "排序并去重",
    command: "sort <FILE> | uniq",
    description: "对文本行排序后去除相邻重复项。",
    keywords: "去重 排序 duplicate unique"
  },
  {
    category: "权限",
    title: "添加执行权限",
    command: "chmod +x script.sh",
    description: "使 Shell 脚本可以直接执行。",
    keywords: "不能执行 permission denied 权限"
  },
  {
    category: "权限",
    title: "查看文件权限",
    command: "ls -l <FILE>",
    description: "查看文件所有者、用户组和读写执行权限。",
    keywords: "权限 owner group rwx"
  },
  {
    category: "压缩",
    title: "压缩目录为 tar.gz",
    command: "tar -czvf archive.tar.gz <DIRECTORY>",
    description: "将目录打包并使用 gzip 压缩。",
    keywords: "压缩文件夹 打包 tar gzip"
  },
  {
    category: "压缩",
    title: "解压 tar.gz",
    command: "tar -xzvf archive.tar.gz",
    description: "解压 gzip 压缩的 tar 包。",
    keywords: "解压缩 tar gz extract"
  },
  {
    category: "传输",
    title: "上传文件到服务器",
    command: "scp <FILE> user@host:/remote/path/",
    description: "通过 SSH 将本地文件复制到远程服务器。",
    keywords: "上传文件 远程 服务器 scp"
  },
  {
    category: "传输",
    title: "下载远程文件",
    command: "scp user@host:/remote/path/<FILE> .",
    description: "通过 SSH 将远程文件下载到当前目录。",
    keywords: "下载文件 服务器 本地 scp"
  },
  {
    category: "传输",
    title: "同步目录并显示进度",
    command: "rsync -avh --progress <SOURCE>/ user@host:<DEST>/",
    description: "增量同步目录到远程服务器并显示进度。",
    keywords: "同步文件夹 断点 增量 transfer"
  },
  {
    category: "进程",
    title: "查看自己的进程",
    command: "ps -u $USER -f",
    description: "列出当前用户的进程及完整启动命令。",
    keywords: "查看进程 process pid"
  },
  {
    category: "进程",
    title: "按名称查找进程",
    command: "pgrep -af <NAME>",
    description: "按名称查找进程，并显示 PID 和完整命令。",
    keywords: "程序是否运行 pid process name"
  },
  {
    category: "进程",
    title: "结束指定进程",
    command: "kill <PID>",
    description: "向进程发送正常终止信号；必要时再考虑 kill -9。",
    keywords: "停止程序 杀进程 terminate"
  },
  {
    category: "进程",
    title: "动态查看进程",
    command: "top -u $USER",
    description: "动态查看当前用户的 CPU 和内存占用。",
    keywords: "实时进程 cpu 内存 top"
  },
  {
    category: "系统",
    title: "查看内存使用",
    command: "free -h",
    description: "以易读单位显示物理内存和交换空间。",
    keywords: "内存剩余 memory swap"
  },
  {
    category: "系统",
    title: "查看 CPU 信息",
    command: "lscpu",
    description: "查看 CPU 架构、核数、线程数和 NUMA 信息。",
    keywords: "处理器 核心数量 cpu cores numa"
  },
  {
    category: "系统",
    title: "查看当前主机名",
    command: "hostname",
    description: "显示当前登录节点或计算节点的主机名。",
    keywords: "哪个节点 主机 node host"
  },
  {
    category: "系统",
    title: "查看环境变量",
    command: "env | sort",
    description: "列出并排序当前 Shell 的环境变量。",
    keywords: "环境配置 variable path"
  },
  {
    category: "环境",
    title: "查看已加载模块",
    command: "module list",
    description: "查看当前环境已经加载的软件模块。",
    keywords: "module 环境 软件版本 loaded"
  },
  {
    category: "环境",
    title: "搜索可用模块",
    command: "module avail 2>&1 | less",
    description: "分页查看集群提供的软件模块。",
    keywords: "查软件 module available"
  },
  {
    category: "环境",
    title: "查找动态库依赖",
    command: "ldd <PROGRAM>",
    description: "查看可执行程序依赖的共享动态库及解析路径。",
    keywords: "找不到 so 动态库 shared library"
  },
  {
    category: "环境",
    title: "临时添加动态库路径",
    command: "export LD_LIBRARY_PATH=/path/to/lib:$LD_LIBRARY_PATH",
    description: "将自定义动态库目录临时加入当前 Shell 搜索路径。",
    keywords: "找不到 so library path export"
  },
  {
    category: "网络",
    title: "查看 IP 地址",
    command: "ip addr",
    description: "查看网络接口和 IP 地址。",
    keywords: "网络地址 ip 网卡"
  },
  {
    category: "网络",
    title: "测试网络连通",
    command: "ping -c 4 <HOST>",
    description: "向目标主机发送 4 个测试包。",
    keywords: "网络通不通 connectivity host"
  },
  {
    category: "网络",
    title: "查看监听端口",
    command: "ss -lntp",
    description: "查看 TCP 监听端口及对应进程。",
    keywords: "端口占用 port listen"
  },
  {
    category: "运行",
    title: "后台运行并保存日志",
    command: "nohup <COMMAND> > run.log 2>&1 &",
    description: "退出终端后继续运行程序，并把标准输出和错误写入日志。",
    keywords: "后台运行 断开继续 nohup log"
  },
  {
    category: "运行",
    title: "查看上一条命令退出码",
    command: "echo $?",
    description: "显示上一条命令的退出状态，0 通常表示成功。",
    keywords: "是否成功 exit status error code"
  },
  {
    category: "Shell",
    title: "查看命令历史",
    command: "history | tail -n 50",
    description: "查看最近执行的 50 条 Shell 命令。",
    keywords: "以前命令 历史记录 history"
  },
  {
    category: "Shell",
    title: "查找命令位置",
    command: "which <COMMAND>",
    description: "查看 Shell 实际调用的可执行文件路径。",
    keywords: "程序路径 executable where"
  }
];
