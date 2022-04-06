# -*- coding: utf-8 -*-
# __author__ = 'zengjing'
# last_modified: 20171130

"""fastx_clipper 用于对SE序列做去接头的工具"""
from biocluster.agent import Agent
from biocluster.tool import Tool
from biocluster.core.exceptions import OptionError
import glob
import re
import os


class FastxClipperAgent(Agent):
    def __init__(self, parent):
        super(FastxClipperAgent, self).__init__(parent)
        options = [
            {"name": "fastq_s", "type": "infile", "format": "sequence.fastq"},  # 输入文件SE序列
            {"name": "fastq_dir", "type": "infile", "format": "sequence.fastq_dir"},  # fastq文件夹
            {"name": "length", "type": "int", "default": 18},  # 最小序列长度，丢弃比此值更短的序列
            {"name": "quality", "type": "string", "default": '35'},
            {"name": "adapter", "type": "string", "default": 'GATCGGAAGAGCACACGTC'},  # 接头序列，如果微量建库，则改为AAAAAA
            {"name": "clip_s", "type": "outfile", "format": "sequence.fastq"},  # SE去接头输出结果
            {"name": "clip_dir", "type": "outfile", "format": "sequence.fastq_dir"},  # fastq文件夹
            {"name": "cut_tail", "type": "int", "default": 0},  # 去掉尾部的fastq
        ]
        self.add_option(options)
        self.step.add_steps('fastx_clipper')
        self.on('start', self.step_start)
        self.on('end', self.step_end)

    def step_start(self):
        self.step.fastx_clipper.start()
        self.step.update()

    def step_end(self):
        self.step.fastx_clipper.finish()
        self.step.update()

    def check_options(self):
        """
        检测参数是否正确
        """
        if not self.option("fastq_dir").is_set and not self.option("fastq_s").is_set:
            raise OptionError("请传入SE序列文件或者文件夹")

    def set_resource(self):
        """
        所需资源
        """
        self._cpu = 4
        self._memory = '30G'


class FastxClipperTool(Tool):
    def __init__(self, config):
        super(FastxClipperTool, self).__init__(config)
        self.fastxtoolkit_path = 'bioinfo/seq/fastx_toolkit_0.0.14/'
        self.python =  "miniconda2/bin/python"
        self.cut_tail = self.config.PACKAGE_DIR + "/small_rna/cut_tail.py"

    def fastxclipper(self):
        fq_s_path = self.option("fastq_s").prop['path']
        file_name = os.path.basename(fq_s_path)
        if re.search('\.gz$', file_name) or re.search('\.gzip$', file_name):
            os.system("gunzip -c {} > {}".format(fq_s_path, "unzip.fq"))
            fq_s_path = self.work_dir + "/unzip.fq"
        if self.option("cut_tail") > 0:
            cmd = self.fastxtoolkit_path + 'fastx_clipper -i {} -a {} -Q 35 -v -l {} -o {}_clip_s.fastq.tmp'.\
                format(fq_s_path, self.option('adapter'), self.option('length'), file_name.split('.')[0])
            self.logger.info("开始运行fastx_clipper")
            self.logger.info(cmd)
            command = self.add_command("fastx_clipper_{}".format(file_name.split('.')[0].lower()), cmd).run()
            self.wait(command)
            if command.return_code == 0:
                self.logger.info("运行fastx_clipper完成")
            else:
                self.set_error("运行fastx_clipper运行出错!")
                return False

            cmd = '{} {} -i {}_clip_s.fastq.tmp -o {}_clip_s.fastq -n {}'.format(self.python, self.cut_tail, file_name.split('.')[0], file_name.split('.')[0], self.option("cut_tail"))
            self.logger.info("开始运行trim_tail")
            self.logger.info(cmd)
            command = self.add_command("trim_tail_{}".format(file_name.split('.')[0].lower()), cmd).run()
            self.wait(command)
            if command.return_code == 0:
                self.logger.info("运行trim_tail完成")
            else:
                self.set_error("运行trim_tail运行出错!")
                return False

        else:
            cmd = self.fastxtoolkit_path + 'fastx_clipper -i {} -a {} -Q {} -v -l {} -o {}_clip_s.fastq'.\
            format(fq_s_path, self.option('adapter'),
                   self.option('quality'),
                   self.option('length'), file_name.split('.')[0])
            self.logger.info("开始运行fastx_clipper")
            self.logger.info(cmd)
            command = self.add_command("fastx_clipper_{}".format(file_name.split('.')[0].lower()), cmd).run()
            self.wait(command)
            if command.return_code == 0:
                self.logger.info("运行fastx_clipper完成")
            else:
                self.set_error("运行fastx_clipper运行出错!")
                return False

    def multi_fastxclipper(self):
        fq_dir = self.option("fastq_dir").prop["path"]
        commands = []
        commands2 = []
        fqs = []
        if "list.txt" in os.listdir(fq_dir):
            with open(fq_list, "r") as l:
                for line in l:
                    line = line.strip().split()
                    fqs.append(line[0])
        else:
            fqs = os.listdir(fq_dir)

        if self.option("cut_tail") > 0:
            for f in fqs:
                file_name = os.path.basename(f)
                fq_s_path = os.path.join(fq_dir, f)
                if re.search('\.gz$', f) or re.search('\.gzip$', f):
                    os.system("gunzip -c {} > {}".format(fq_s_path, os.path.basename(fq_s_path).split('.gz')[0]))
                    fq_s_path = os.path.join(self.work_dir, os.path.basename(fq_s_path).split('.gz')[0])
                cmd = self.fastxtoolkit_path + 'fastx_clipper -i {} -a {} -Q 35 -v -l {} -o {}_clip_s.fastq.tmp'.\
                    format(fq_s_path, self.option('adapter'), self.option('length'), file_name.split('.')[0])
                self.logger.info("开始运行fastx_clipper")
                self.logger.info(cmd)
                command = self.add_command("fastx_clipper_{}".format(file_name.split('.')[0].lower()), cmd).run()
                commands.append(command)
            self.wait()

            for cmd in commands:
                if cmd.return_code == 0:
                    self.logger.info("运行{}完成".format(cmd.name))
                else:
                    self.set_error("运行{}运行出错!".format(cmd.name))
                    raise Exception("运行{}运行出错!".format(cmd.name))

            for f in fqs:
                fq_s_path = os.path.join(fq_dir, f)
                file_name = os.path.basename(f)
                cmd = self.fastxtoolkit_path + '{} {} -i {}_clip_s.fastq.tmp -o {}_clip_s.fastq -n {}'.\
                    format(fq_s_path, self.option('adapter'), self.option('length'), f.split('.')[0], self.python, self.cut_tail, file_name.split('.')[0], file_name.split('.')[0], self.option("cut_tail"))
                self.logger.info("开始运行fastx_clipper")
                self.logger.info(cmd)
                command = self.add_command("fastx_clipper_{}".format(f.split('.')[0].lower()), cmd).run()
                commands2.append(command)
            self.wait()
            for cmd in commands2:
                if cmd.return_code == 0:
                    self.logger.info("运行{}完成".format(cmd.name))
                else:
                    self.set_error("运行{}运行出错!".format(cmd.name))
                    raise Exception("运行{}运行出错!".format(cmd.name))

        else:
            for f in fqs:
                fq_s_path = os.path.join(fq_dir, f)
                if re.search('\.gz$', f) or re.search('\.gzip$', f):
                    os.system("gunzip -c {} > {}".format(fq_s_path, os.path.basename(fq_s_path).split('.gz')[0]))
                    fq_s_path = os.path.join(self.work_dir, os.path.basename(fq_s_path).split('.gz')[0])
                cmd = self.fastxtoolkit_path + 'fastx_clipper -i {} -a {} -Q 35 -v -l {} -o {}_clip_s.fastq'.\
                    format(fq_s_path, self.option('adapter'), self.option('length'), f.split('.')[0])
                self.logger.info("开始运行fastx_clipper")
                self.logger.info(cmd)
                command = self.add_command("fastx_clipper_{}".format(f.split('.')[0].lower()), cmd).run()
                commands.append(command)
            self.wait()

            for cmd in commands:
                if cmd.return_code == 0:
                    self.logger.info("运行{}完成".format(cmd.name))
                else:
                    self.set_error("运行{}运行出错!".format(cmd.name))
                    raise Exception("运行{}运行出错!".format(cmd.name))

    def reads_stat(self):
        """统计fastx_clipper出来的结果.o文件里的信息"""
        out = {}
        for f in os.listdir(self.output_dir):
            s = f.split("_clip_s.fastq")[0].lower()
            out[s] = f.split("_clip_s.fastq")[0]
        files = glob.glob(r'fastx_clipper*.o')
        with open(os.path.join(self.output_dir, "Sample_QC_stat.xls"), "w") as w:
            w.write("Sample\tRaw_reads\tAdapter_only\tN_reads\t<18nt\t>32nt\tClean_reads\tAdapter%\n")
            for f in files:
                s = f.split(".")[0].split("fastx_clipper_")[1]
                line = out[s] + "\t"
                with open(f, "r") as f:
                    raw_reads, short_reads, adapter_only, n_reads, less_reads, big_reads, clean_reads = 0, 0, 0, 0, 0, 0, 0
                    for line in f:
                        if re.match(r"Input", line):
                            raw_reads = line.strip().split()[1]
                        if re.match(r"discarded.*too-short reads", line):
                            short_reads = line.strip().split()[1]
                        if re.match(r"discarded.*adapter-only reads", line):
                            adapter_only = line.strip().split()[1]
                        if re.match(r"discarded.*N reads", line):
                            n_reads = line.strip().split()[1]
                        if re.match(r"discarded.*too-short reads", line):
                            less_reads = line.strip().split()[1]
                        if re.match(r"discarded.*bigger than 32 reads", line):
                            big_reads = line.strip().split()[1]
                        if re.match(r"remain.*clean reads", line):
                            clean_reads = line.strip().split()[1]
                    eighteen = int(short_reads) + int(less_reads)
                    adapter_rate = round(float(adapter_only) / int(raw_reads), 4) * 100
                    w.write(out[s] + "\t" + str(raw_reads) + "\t" + str(adapter_only) + "\t" + str(n_reads) + "\t"\
                            + str(eighteen) + "\t" + str(big_reads) + "\t" + str(clean_reads) + "\t" + str(adapter_rate) + "\n")

    def set_output(self):
        """
        将结果文件链接至output
        """
        self.logger.info("set output")
        file_path = glob.glob(r"*.fastq")
        for f in file_path:
            output_dir = os.path.join(self.output_dir, f)
            if os.path.exists(output_dir):
                os.remove(output_dir)
            os.link(os.path.join(self.work_dir, f), output_dir)
            self.option("clip_s").set_path(output_dir)
        if self.option("fastq_dir").is_set:
            self.option("clip_dir").set_path(self.output_dir)
        self.logger.info("done")

    def run(self):
        """
        运行
        """
        super(FastxClipperTool, self).run()
        if self.option("fastq_dir").is_set:
            self.multi_fastxclipper()
            self.set_output()
        else:
            self.fastxclipper()
            self.set_output()
        self.reads_stat()
        self.end()
