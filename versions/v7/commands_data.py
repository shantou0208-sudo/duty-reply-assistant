"""v7 内置命令库。用户新增内容保存在本地 SQLite，不会修改本文件。"""

DEFAULT_COMMANDS = [
    # 文件与目录
    ("Linux·文件", "查看当前目录", "pwd", "显示当前所在目录的绝对路径。", "路径 当前目录"),
    ("Linux·文件", "列出文件", "ls -lah", "以易读格式显示隐藏文件、权限和大小。", "文件 列表 隐藏"),
    ("Linux·文件", "按时间排序", "ls -lht", "按修改时间从新到旧列出文件。", "时间 最新"),
    ("Linux·文件", "进入目录", "cd /path/to/dir", "切换到指定目录。", "切换 目录"),
    ("Linux·文件", "返回上级", "cd ..", "返回上一级目录。", "上级 返回"),
    ("Linux·文件", "返回家目录", "cd ~", "返回当前用户家目录。", "home 家目录"),
    ("Linux·文件", "创建目录", "mkdir -p path/to/dir", "递归创建目录。", "新建 文件夹"),
    ("Linux·文件", "复制文件", "cp source destination", "复制单个文件。", "复制"),
    ("Linux·文件", "复制目录", "cp -a source_dir destination_dir", "保留属性递归复制目录。", "复制 文件夹"),
    ("Linux·文件", "移动或重命名", "mv old_name new_name", "移动文件，也可用于重命名。", "移动 改名"),
    ("Linux·文件", "删除文件", "rm file", "删除文件，执行前确认路径。", "删除"),
    ("Linux·文件", "删除空目录", "rmdir directory", "仅删除空目录。", "删除 文件夹"),
    ("Linux·文件", "查找文件", "find . -type f -name '*.log'", "在当前目录递归查找匹配文件。", "搜索 文件"),
    ("Linux·文件", "查找最近文件", "find . -type f -mtime -1", "查找最近 24 小时修改的文件。", "最近 修改"),
    ("Linux·文件", "查看文件类型", "file filename", "识别文件类型。", "类型"),
    ("Linux·文件", "创建软链接", "ln -s target link_name", "为目标创建符号链接。", "软链接 link"),
    # 查看与文本处理
    ("Linux·文本", "查看文件", "less filename", "分页查看文件，q 退出，/关键词搜索。", "查看 内容"),
    ("Linux·文本", "查看文件开头", "head -n 20 filename", "显示前 20 行。", "开头 前几行"),
    ("Linux·文本", "查看文件结尾", "tail -n 50 filename", "显示最后 50 行。", "结尾 后几行"),
    ("Linux·文本", "实时查看日志", "tail -f filename.log", "持续显示日志新增内容，Ctrl+C 结束。", "日志 实时"),
    ("Linux·文本", "搜索文本", "grep -n 'keyword' filename", "显示关键词及行号。", "关键词 查找"),
    ("Linux·文本", "递归搜索文本", "grep -Rni 'keyword' directory", "递归搜索目录，忽略大小写并显示行号。", "递归 查找"),
    ("Linux·文本", "统计行数", "wc -l filename", "统计文件行数。", "行数 统计"),
    ("Linux·文本", "排序去重", "sort filename | uniq", "排序后去除相邻重复行。", "排序 去重"),
    ("Linux·文本", "提取列", "awk '{print $1}' filename", "输出以空白分隔的第一列。", "列 awk"),
    ("Linux·文本", "替换文本", "sed 's/old/new/g' filename", "预览将 old 替换为 new 的结果，不改原文件。", "替换 sed"),
    ("Linux·文本", "比较文件", "diff -u old_file new_file", "以统一格式比较两个文本文件。", "对比 差异"),
    # 磁盘与内存
    ("Linux·资源", "查看文件大小", "du -h filename", "查看文件或目录占用空间。", "大小"),
    ("Linux·资源", "查看目录总大小", "du -sh directory", "汇总目录占用空间。", "文件夹 大小"),
    ("Linux·资源", "查看一级子目录大小", "du -h --max-depth=1 directory | sort -h", "统计一级子目录并按大小排序。", "目录 大小 排序"),
    ("Linux·资源", "查看磁盘空间", "df -h", "查看各文件系统容量与剩余空间。", "磁盘 剩余"),
    ("Linux·资源", "查看内存", "free -h", "查看内存和交换分区使用量。", "内存 memory"),
    ("Linux·资源", "动态查看资源", "top", "动态查看 CPU、内存和进程。", "cpu 内存 进程"),
    ("Linux·资源", "友好资源监控", "htop", "交互式资源监控；系统需安装 htop。", "cpu 内存 htop"),
    ("Linux·资源", "查看 GPU", "nvidia-smi", "查看 NVIDIA GPU、显存和进程。", "gpu 显存"),
    ("Linux·资源", "持续查看 GPU", "watch -n 1 nvidia-smi", "每秒刷新 GPU 状态。", "gpu 实时"),
    # 进程与权限
    ("Linux·进程", "查看自己的进程", "ps -u \"$USER\" -f", "查看当前用户的进程。", "进程"),
    ("Linux·进程", "查找进程", "ps aux | grep process_name", "按名称查找进程。", "进程 搜索"),
    ("Linux·进程", "结束进程", "kill PID", "请求进程正常退出。", "终止"),
    ("Linux·进程", "强制结束进程", "kill -9 PID", "强制结束无响应进程，谨慎使用。", "强制 终止"),
    ("Linux·进程", "后台运行", "nohup command > run.log 2>&1 &", "脱离终端后台运行并保存输出。", "后台 nohup"),
    ("Linux·权限", "查看权限", "ls -l filename", "查看文件所有者和读写执行权限。", "权限"),
    ("Linux·权限", "添加执行权限", "chmod +x script.sh", "允许执行脚本。", "执行 chmod"),
    ("Linux·权限", "修改权限", "chmod 750 filename", "所有者读写执行、同组读执行、其他用户无权限。", "chmod"),
    ("Linux·权限", "修改所有者", "chown user:group filename", "修改文件所有者和用户组，通常需要管理员权限。", "owner 所有者"),
    # 压缩、网络和环境
    ("Linux·压缩", "打包压缩", "tar -czvf archive.tar.gz directory", "创建 tar.gz 压缩包。", "压缩 打包"),
    ("Linux·压缩", "解压 tar.gz", "tar -xzvf archive.tar.gz", "解压 tar.gz 文件。", "解压"),
    ("Linux·压缩", "压缩 ZIP", "zip -r archive.zip directory", "递归创建 ZIP。", "zip 压缩"),
    ("Linux·压缩", "解压 ZIP", "unzip archive.zip", "解压 ZIP 文件。", "zip 解压"),
    ("Linux·网络", "测试连通性", "ping -c 4 hostname", "发送 4 个 ICMP 请求。", "网络 ping"),
    ("Linux·网络", "下载文件", "wget URL", "从 URL 下载文件。", "下载 wget"),
    ("Linux·网络", "curl 下载", "curl -L -O URL", "跟随跳转并保留远端文件名。", "下载 curl"),
    ("Linux·网络", "查看端口", "ss -lntp", "查看监听中的 TCP 端口和进程。", "端口"),
    ("Linux·网络", "SSH 登录", "ssh user@hostname", "通过 SSH 登录远程服务器。", "登录 远程"),
    ("Linux·网络", "SCP 上传", "scp local_file user@host:/remote/path/", "上传文件到远端。", "上传 scp"),
    ("Linux·网络", "SCP 下载", "scp user@host:/remote/file .", "下载远端文件到当前目录。", "下载 scp"),
    ("Linux·环境", "查看环境变量", "env | sort", "列出并排序环境变量。", "环境变量"),
    ("Linux·环境", "临时设置环境变量", "export NAME=value", "仅对当前 Shell 及其子进程生效。", "export"),
    ("Linux·环境", "查找命令位置", "which command", "显示命令对应的可执行文件路径。", "路径 which"),
    ("Linux·环境", "查看动态库依赖", "ldd executable", "查看程序依赖的共享库。", "so 动态库"),
    ("Linux·环境", "临时添加动态库路径", "export LD_LIBRARY_PATH=/path/to/lib:$LD_LIBRARY_PATH", "临时解决找不到 .so 文件的问题。", "so 动态库"),
    ("Linux·环境", "查看模块", "module avail", "查看集群可用的软件环境模块。", "module 软件"),
    ("Linux·环境", "已加载模块", "module list", "查看当前加载的模块。", "module"),
    ("Linux·环境", "加载模块", "module load module/name", "加载指定软件模块。", "module load"),
    ("Linux·环境", "清空模块", "module purge", "卸载当前加载的全部环境模块。", "module purge"),
    # Conda
    ("Conda", "查看 Conda 版本", "conda --version", "显示 Conda 版本。", "版本"),
    ("Conda", "查看环境列表", "conda env list", "列出全部 Conda 环境及路径。", "环境 列表"),
    ("Conda", "创建环境", "conda create -n myenv python=3.12", "创建名为 myenv 的 Python 环境。", "新建 环境"),
    ("Conda", "激活环境", "conda activate myenv", "激活指定环境。", "进入 激活"),
    ("Conda", "退出环境", "conda deactivate", "退出当前环境。", "退出"),
    ("Conda", "删除环境", "conda env remove -n myenv", "删除指定环境。", "删除 环境"),
    ("Conda", "克隆环境", "conda create -n newenv --clone oldenv", "完整克隆已有环境。", "复制 克隆"),
    ("Conda", "安装软件包", "conda install -n myenv package_name", "向指定环境安装软件包。", "安装 包"),
    ("Conda", "指定渠道安装", "conda install -c conda-forge package_name", "从 conda-forge 安装。", "channel 渠道"),
    ("Conda", "查看已安装包", "conda list -n myenv", "列出指定环境的软件包。", "包 列表"),
    ("Conda", "搜索软件包", "conda search package_name", "搜索可安装的软件包版本。", "搜索 包"),
    ("Conda", "更新软件包", "conda update package_name", "更新当前环境中的软件包。", "更新"),
    ("Conda", "导出环境", "conda env export --no-builds > environment.yml", "导出较易跨平台复现的环境文件。", "导出 yml"),
    ("Conda", "从文件创建环境", "conda env create -f environment.yml", "根据 YAML 文件创建环境。", "导入 yml"),
    ("Conda", "清理缓存", "conda clean --all", "清理索引、包缓存和无用文件，执行前确认。", "缓存 清理"),
    ("Conda", "初始化 Shell", "conda init bash", "为 Bash 配置 conda activate。", "初始化 activate"),
    # Slurm 查询与控制
    ("Slurm·作业", "查看自己的作业", "squeue -u \"$USER\"", "查看当前用户排队和运行中的作业。", "队列 作业"),
    ("Slurm·作业", "自定义作业格式", "squeue -u \"$USER\" -o '%.18i %.12P %.24j %.8T %.10M %.6D %R'", "显示作业号、队列、名称、状态、时间、节点数和原因。", "队列 原因"),
    ("Slurm·作业", "查看作业详情", "scontrol show job JOBID", "查看作业资源、状态和排队原因。", "详情"),
    ("Slurm·作业", "查看节点", "sinfo -N -l", "按节点显示分区、状态和资源。", "节点 node"),
    ("Slurm·作业", "查看分区", "sinfo", "查看分区及节点状态概览。", "partition 队列"),
    ("Slurm·作业", "取消作业", "scancel JOBID", "取消指定作业。", "取消"),
    ("Slurm·作业", "取消自己的全部作业", "scancel -u \"$USER\"", "取消当前用户全部作业，谨慎使用。", "全部 取消"),
    ("Slurm·作业", "查看历史作业", "sacct -u \"$USER\" --starttime today", "查看今天的历史作业记录。", "历史 sacct"),
    ("Slurm·作业", "查看资源效率", "seff JOBID", "查看作业 CPU 和内存利用率；部分集群可能未安装。", "效率 内存"),
    ("Slurm·作业", "交互申请", "salloc -p partition -N 1 -n 1 -t 01:00:00", "申请一个节点的交互资源。", "交互 salloc"),
    ("Slurm·作业", "进入已分配节点", "srun --pty bash", "在已有分配中启动交互 Shell。", "交互 srun"),
    ("Slurm·作业", "提交脚本", "sbatch job.sh", "提交 Slurm 作业脚本。", "提交"),
    # Slurm 脚本参数
    ("Slurm·参数", "作业名称", "#SBATCH --job-name=myjob", "设置作业名称。", "job-name 名称"),
    ("Slurm·参数", "分区/队列", "#SBATCH --partition=partition_name", "指定作业分区。也可写作 -p。", "partition 队列"),
    ("Slurm·参数", "节点数", "#SBATCH --nodes=1", "申请节点数量。也可写作 -N。", "nodes 节点"),
    ("Slurm·参数", "总任务数", "#SBATCH --ntasks=64", "设置 MPI 总进程数。也可写作 -n。", "ntasks mpi 进程"),
    ("Slurm·参数", "每节点任务数", "#SBATCH --ntasks-per-node=64", "设置每个节点的 MPI 进程数。", "mpi 进程"),
    ("Slurm·参数", "每任务 CPU", "#SBATCH --cpus-per-task=8", "为每个任务申请 CPU 线程，常用于 OpenMP。", "cpu 线程 omp"),
    ("Slurm·参数", "运行时间", "#SBATCH --time=24:00:00", "设置最长运行时间，格式通常为 天-时:分:秒。", "time 时间"),
    ("Slurm·参数", "内存", "#SBATCH --mem=64G", "设置每个节点申请的总内存。", "memory 内存"),
    ("Slurm·参数", "每 CPU 内存", "#SBATCH --mem-per-cpu=4G", "按每个 CPU 核申请内存，不要与 --mem 同时使用。", "内存"),
    ("Slurm·参数", "申请 GPU", "#SBATCH --gres=gpu:1", "申请 1 张 GPU；具体写法以集群规则为准。", "gpu 显卡"),
    ("Slurm·参数", "指定 GPU 类型", "#SBATCH --gres=gpu:a100:2", "申请 2 张 A100；仅在集群配置支持时使用。", "gpu a100"),
    ("Slurm·参数", "标准输出", "#SBATCH --output=%x-%j.out", "%x 为作业名，%j 为作业号。", "输出 日志"),
    ("Slurm·参数", "标准错误", "#SBATCH --error=%x-%j.err", "单独保存错误输出。", "错误 日志"),
    ("Slurm·参数", "邮件通知", "#SBATCH --mail-type=BEGIN,END,FAIL", "在开始、结束或失败时发送邮件。", "邮件"),
    ("Slurm·参数", "邮件地址", "#SBATCH --mail-user=name@example.com", "指定通知邮箱。", "邮箱"),
    ("Slurm·参数", "指定节点", "#SBATCH --nodelist=node01", "指定节点，通常不建议日常使用。", "节点 指定"),
    ("Slurm·参数", "排除节点", "#SBATCH --exclude=node01", "排除故障或不适用节点。", "节点 排除"),
    ("Slurm·参数", "作业依赖", "#SBATCH --dependency=afterok:JOBID", "仅在前置作业成功后运行。", "依赖"),
    ("Slurm·模板", "CPU MPI 作业模板", """#!/bin/bash
#SBATCH --job-name=myjob
#SBATCH --partition=partition_name
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=64
#SBATCH --time=24:00:00
#SBATCH --output=%x-%j.out

module purge
module load your/module
mpirun -np "$SLURM_NTASKS" your_program""", "单节点 MPI 作业模板，请按集群修改分区、模块和程序。", "脚本 mpi cpu"),
    ("Slurm·模板", "GPU 作业模板", """#!/bin/bash
#SBATCH --job-name=gpu_job
#SBATCH --partition=gpu_partition
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
#SBATCH --time=24:00:00
#SBATCH --output=%x-%j.out

module purge
module load cuda
python your_script.py""", "单节点单 GPU 模板，请按集群修改队列和模块。", "脚本 gpu python"),
]
