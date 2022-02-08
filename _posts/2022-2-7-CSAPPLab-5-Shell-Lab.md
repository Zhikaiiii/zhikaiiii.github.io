---
title: 'CSAPPLab(5): Shell Lab'
mathjax: false
date: 2022-02-07 15:49:09
tags:
    - CSAPP
    - 课程学习
categories:
    - 课程学习
---
<style> h1 { border-bottom: none } </style>
<style> h2 { border-bottom: none } </style>

<!-- more -->

# 实验介绍

本次实验需要实现一个简单的Shell程序`tsh`，该Shell程序包含内置命令`quit`(退出)，`jobs`(列出进程),`fg`(将一个进程转换为前台运行), `bg`(将一个进程在后台继续运行)，此外还能运行外部的程序和命令。除此之外，其还能正常的处理`SIGINT, SIGTSTP, SIGCHLD, SIGCONT`等信号。
实验的评估共有16个小任务，任务`i`可以通过`make test$i`快速查看输出结果，而`make rtest$i`可以查看参考答案的输出结果，也可也直接在`tshref.out`文件中直接查看结果。
实验的所有代码都在`tsh.c`中完成，另外有四个小测试程序，分别为

* `myspin.c`: 休眠`i`秒后结束进程
* `mysplit.c`: 创建子进程并休眠`i`秒后结束，父进程等待子进程的结束。
* `mystop.c`: 休眠`i`秒后，发送`SIGTSTP`信号给进程使其停止。
* `myint.c`: 休眠`i`秒后，发送`SIGINT`信号给进程使其终止。

# 解答

## 整体流程

该Shell程序的整体流程为：在主函数`main`的循环中，每次从`stdin`获取输入的命令，用`eval`函数进行处理。`eval`函数首先对输入的命令调用`parseline`函数进行解析，转换为`argv`的参数列表形式，其中`argv[0]`为命令，并根据`&`判断程序是否在后台运行。
若任务在后台运行，函数会输出对应的进程信息。如果在前台进行，则调用`waitfg`等待任务的完成。

```C
void waitfg(pid_t pid)
{
    while (pid == fgpid(jobs))
    {
        sleep(1);
    }
    return;
}
```

## 任务管理

Shell程序需要对现在的进程和任务进行管理，因此提供了一个`job_t`的结构体，其结构如下：

```C
struct job_t {              /* The job struct */
    pid_t pid;              /* job PID */
    int jid;                /* job ID [1, 2, ...] */
    int state;              /* UNDEF, BG, FG, or ST */
    char cmdline[MAXLINE];  /* command line */
};
```

此外，还提供了添加、删除任务，获取任务信息等函数方便调用。

## 命令执行

命令执行部分分为两部分，内置命令和其他命令。
内置命令基于`builtin_cmd`函数完成，通过字符串比较判断对应需要执行的函数，如`jobs`命令对应`listjobs`函数，`fg,bg`命令执行`do_bgfg`函数。
`do_bgfg`函数需要完成对指定任务/进程状态的切换，使进程继续运行(原先的状态可能是停止或运行)。因此，需要发送`SIGCONT`信号给进程，并相应的修改任务状态。

```C
if(!strcmp(argv[0], "bg"))
{
    kill(-(curr_job->pid), SIGCONT);
    curr_job->state = BG;
    printf("[%d] (%d) %s",curr_job->jid, curr_job->pid, curr_job->cmdline);
}
else
{
    kill(-(curr_job->pid), SIGCONT);
    curr_job->state = FG;
    waitfg(curr_job->pid);
}
```

其他命令通过`fork`函数和`exceve`函数配合使用完成。注意，为了保证后面给进程发送信号时，进程的子进程能够收到信号，需要对进程的进程组ID进行设置。如下

```C
// excute cmd
if((pid = fork()) == 0){
    sigprocmask(SIG_SETMASK, &prev_mask, NULL); // unblock SIGCHLD
    setpgid(0, 0); // set pgid
    if(execve(argv[0], argv, environ) < 0){
        printf("%s: Command not found\n", argv[0]);
        exit(0);
    }
}
```

## 信号处理

一共需要完成三个信号处理函数，在信号处理函数中开始时先对所有信号进行了阻塞，避免信号处理函数被中断，函数结束后取消阻塞。
实现的过程中还有几个细节。首先是最开始，任务的删除`deletejob`在`sigint_handler`调用，进程暂停的状态修改`curr_job->state = ST;`在`sigtstp_handler`中完成。但是这样做的问题在于：1) 实际上调用这两个函数后，进程停止或终止时，会给父进程发送一个`SIGCHLD`信号，从而进入`sigchld_handler`函数。2) 在测试样例中，包含了由外部程序发送的`SIGINT`和`SIGTSTP`信号，这样的信号是无法被Shell程序捕捉的。(参考另外开一个bash终端，然后`kill -20 xxx`)，但是进程停止或终止的`SIGCHLD`信号是可以被捕捉的，因此将对应的`deletejob`移到了`sigchld_handler`函数中进行处理。
其次，`sigchld_handler`函数中的`waitpid`不能只调用一次，这是因为在处理时可能有多个同样的信号到达，但是由于信号的非排队机制导致部分信号丢失。因此需要用`while`循环保证所有的子进程被回收。使用`WNOHANG | WUNTRACED`能够获取所有终止或停止的子进程ID，如果没有的话则返回0。

```C
void sigchld_handler(int sig) 
{
    sigset_t mask, prev_mask;
    sigfillset(&mask);
    sigprocmask(SIG_BLOCK, &mask, &prev_mask);

    pid_t pid;
    int status;
    while((pid = waitpid(-1, &status, WNOHANG | WUNTRACED)) > 0){
        
        // 被未捕获的信号终止
        if(WIFSIGNALED(status)){
            // struct job_t * curr_job = getjobpid(jobs, pid);
            int jid = pid2jid(pid);
            printf("Job [%d] (%d) terminated by signal 2\n", jid, pid);
            deletejob(jobs, pid);
        }
        // 判断进程停止时的处理
        else if(WIFSTOPPED(status)){
            struct job_t * curr_job = getjobpid(jobs, pid);
            int jid = pid2jid(pid);
            curr_job->state = ST;
            printf("Job [%d] (%d) stopped by signal 20\n", jid, pid);
        }
        else{
            deletejob(jobs, pid);
        }
    }
    sigprocmask(SIG_SETMASK, &prev_mask, NULL);
    return;
}
```

此外，为了防止在`addjob`执行之前子进程任务就已经完成，导致`deletejob`的调用在`addjob`之前。需要在`addjob`之前对`SIGCHLD`信号进行阻塞，调用完毕后再取消阻塞。同时，由于`fork`进程会继承父进程的阻塞情况，因此`fork`后也要取消对`SIGCHLD`的阻塞。

```C
// block SIGCHLD
sigprocmask(SIG_BLOCK, &mask, &prev_mask);
// excute cmd
if((pid = fork()) == 0){
    sigprocmask(SIG_SETMASK, &prev_mask, NULL); // unblock SIGCHLD
    setpgid(0, 0); // set pgid
    if(execve(argv[0], argv, environ) < 0){
        printf("%s: Command not found\n", argv[0]);
        exit(0);
    }
}
int state = bg + 1;
// printf("bg %d pid %d\n", bg, pid);
sigprocmask(SIG_BLOCK, &mask_all, NULL);
addjob(jobs, pid, state, cmdline);
sigprocmask(SIG_SETMASK, &prev_mask, NULL); // unblock SIGCHLD
```