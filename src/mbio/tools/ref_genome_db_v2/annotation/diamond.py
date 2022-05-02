# -*- coding: utf-8 -*-
# __author__ = 'shijin'

from biocluster.agent import Agent
from biocluster.tool import Tool
import os
import re
import shutil
import sqlite3
import xml.etree.ElementTree as ET
import cPickle as cpickle
from biocluster.config import Config
from biocluster.core.exceptions import OptionError
from mbio.packages.rna.annot_config import AnnotConfig

class DiamondAgent(Agent):
    '''
    last_modify: 2019.04.11
    '''
    def __init__(self, parent):
        super(DiamondAgent, self).__init__(parent)
        options = [
            {"name": "query", "type": "infile", "format": "ref_rna_v2.common"},  # 输入文件
            {"name": "query_type", "type": "string", "default": "nucl"},  # 输入的查询序列的格式，为nucl或者prot
            {"name": "database", "type": "string", "default": "plant"},
            # 比对数据库 plant, nr, etc.
            {"name": "outfmt", "type": "int", "default": 5},  # 输出格式，数字默认为5，输出xml
            {"name": "outxml", "type": "outfile", "format": "ref_rna_v2.blast_xml"},
            {"name": "blast", "type": "string", "default": "blastp"},  # 设定diamond程序有blastp，blastx
            {"name": "reference", "type": "infile", "format": "ref_rna_v2.fasta"},  # 参考序列  选择customer时启用
            {"name": "evalue", "type": "float", "default": 1e-5},  # evalue值
            {"name": "num_threads", "type": "int", "default": 20},  # cpu数
            {'name': 'kegg_version', 'type': 'string', 'default': "2019"},
            {"name": "nr_version", "type": "string", "default": "2019"},
            {"name": "swissprot_version", "type": "string", "default": "2019"},
            {"name": "eggnog_version", "type": "string", "default": "2019"},
            {"name": "string_version", "type": "string", "default": "2019"},
            {"name": "sensitive", "type": "int", "default": 2},
            {"name": "version", "type": "string", "default": "2019"},
            {"name": "diamond_version", "type": "string", "default": "v2.0.4"},
            ]
        self.add_option(options)
        self._memory_increase_step = 50
        self.step.add_steps('diamond')
        self.on('start', self.step_start)
        self.on('end', self.step_end)
        self.queue = 'BLAST'  # 投递到指定的队列BLAST

    def step_start(self):
        self.step.diamond.start()
        self.step.update()

    def step_end(self):
        self.step.diamond.finish()
        self.step.update()

    def check_options(self):
        if not self.option("query").is_set:
            raise OptionError("必须设置参数query", code="33700801")
        if self.option('query_type') not in ['nucl', 'prot']:
            raise OptionError('query_type查询序列的类型为nucl(核酸)或者prot(蛋白):%s', variables = (self.option('query_type')), code="33700802")
        if not 1 > self.option('evalue') >= 0:
            raise OptionError('E-value值设定必须为[0-1)之间：%s', variables = (self.option('evalue')), code="33700803")
        if not 0 <= self.option("sensitive") <= 2:
            raise OptionError('敏感度设定必须为[0-2]之间：%s', variables = (self.option('evalue')), code="33700804")
        return True

    def set_resource(self):
        self._cpu = self.option('num_threads')
        self._memory = '15G'
        if self.option("database") == "nr":
            self._memory = '60G'

    def end(self):
        super(DiamondAgent, self).end()


class DiamondTool(Tool):
    def __init__(self, config):
        super(DiamondTool, self).__init__(config)
        self._version = "0.9.24"
        self.get_db_path()
        # self.db_path = os.path.join(self.config.SOFTWARE_DIR, "database/Annotation/latest")
        # 目前这个逻辑一年升级一次没有问题

        '''
        if self.option("database") == 'animal':
            self.option("database", "metazoa")
        elif self.option("database") == 'plant':
            self.option("database", "viridiplantae")
        
        if self.option("database") in ["Algaedmnd",
                                       "Amphibia",
                                       "archaea",
                                       "Aves",
                                       "eukaryota",
                                       "Fishes",
                                       "fungi",
                                       "Invertebrate",
                                       "Mammalia",
                                       "metazoa",
                                       "nr",
                                       "OtherPlant",
                                       "protist",
                                       "Reptilia",
                                       "Spermatophyta",
                                       "viridiplantae",
                                       "viroids",
                                       "viruses"]:
            version_path = "latest2019"

            if self.option("nr_version") !=  "":
                version_path = "latest{}".format(self.option("nr_version"))
            
        elif self.option("database") not in ["kegg"]:
            version_path = "latest2019"
            try:
                if self.option("{}_version".format(self.option("database"))) !=  "":
                    version_path = "latest{}".format(self.option("{}_version".format(self.option("database"))))
            except:
                pass
                

        if self.option("database") == "kegg":
            version_path = "latest2019"
            if self.option("kegg_version") in ["202003"]:
                version_path = 'other{}/kegg{}'.format(self.option("kegg_version")[0:4], self.option("kegg_version"))
        '''

        if self.option("diamond_version") == "v2.0.4":
            self.cmd_path = "bioinfo/rna/miniconda2_diamond/bin"
        elif self.option("diamond_version") == "v0.9.24.125":
            self.cmd_path = "miniconda2/bin"
        else:
            self.cmd_path = "bioinfo/align/diamond-0.8.35" 

        if self.option("query_type") == "nucl":
            self.blast_type = "blastx"
        else:
            self.blast_type = "blastp"
        self.mongodb_nr = Config().get_mongo_client(mtype="ref_rna", ref=True)[Config().get_mongo_dbname("ref_rna", ref=True)].NR_sequence
        self.ori = []
        self.repl = []

    def get_db_path(self):
        sub_dict = dict()
        for sub_version in ['kegg_version', 'nr_version', 'swissprot_version', 'eggnog_version', 'string_version']:
            sub_dict.update({sub_version: self.option(sub_version)})

        self.db_path = AnnotConfig().get_dmnd_path(db_name=self.option("database"),
                                                   version=self.option("version"),
                                                   **sub_dict)
        return self.db_path


    def run(self):
        super(DiamondTool, self).run()
        if self.option("database") == 'customer_mode':
            self.run_makedb_and_diamond()
        else:
            self.run_diamond(self.option("database"))
        self.change_version(self.outputfile)

    def run_makedb_and_diamond(self):
        db_name = os.path.splitext(os.path.basename(self.option("reference").prop['path']))[0]
        cmd = os.path.join(self.cmd_path, "diamond")
        self.db_path = os.path.join(self.work_dir, db_name)

        cmd += " makedb --in {} --db {}".format(self.option("reference").prop['path'], db_name)
        self.logger.info("开始创建diamond数据库，生成结果库文件放在工作目录的customer_blastdb下")
        makedb_obj = self.add_command("makedb", cmd, ignore_error=True).run()
        self.wait(makedb_obj)
        if makedb_obj.return_code == 0:
            self.logger.info("创建diamond数据库完成")
            self.run_diamond(db_name)
        elif makedb_obj.return_code in [1, -9]:  # add memory limit by shicaiping at 20180724
            self.add_state("memory_limit", "memory is low!")
        else:
            self.set_error("创建diamond数据库出错!", code="33700805")

    def run_diamond(self, db_name):
        db = self.db_path
        query_name = os.path.splitext(os.path.basename(self.option("query").prop['path']))[0]
        cmd = os.path.join(self.cmd_path, "diamond")
        outputfile = os.path.join(self.output_dir, query_name + "_vs_" + db_name)
        outfmt = self.option('outfmt')
        # if self.option('outfmt') == 5:
        outputfile += '.xml'  # outfmt默认为5
        outfmt = 5
        # 2019.04.11 add for skipping if that error occurs
        # if os.path.getsize(outputfile) and os.path.isfile(os.path.join(self.work_dir, 'Diamond.confirm')):
        #     self.change_version(outputfile)
        cmd += " {} -q {} -d {} -o {} -e {} -f {} -p {} -k 15".format(
            self.blast_type, self.option("query").prop['path'], db, outputfile,
            self.option("evalue"), outfmt, self.option("num_threads"))
        if self.option("sensitive") == 1:
            cmd += " --sensitive"
        elif self.option("sensitive") == 2:
            cmd += " --more-sensitive"
        cmd_name = 'run_diamond'
        self.run_code(cmd_name, cmd)
        self.outputfile = outputfile

    def get_nrxml_gi_description(self, xml_path):
        """
        从参考库NR_sequence中找到gi号对应的description
        """
        if self.option("database") != "swissprot":
            nracc2des = os.path.dirname(self.db_path) + "/nr_acc2des.db"
            if os.path.exists(nracc2des):
                pass
            else:
                nracc2des = AnnotConfig().get_file_path(
                    file="nr_acc2des.db",
                    db="nr",
                    db_type="file",
                    version=self.option("nr_version"))
        if self.option("database") == "swissprot":
            nracc2des = os.path.dirname(self.db_path) + "/swissprot_acc2des.db"
            if os.path.exists(nracc2des):
                pass
            else:
                nracc2des = AnnotConfig().get_file_path(
                    file="swissprot_acc2des.db",
                    db="swissprot",
                    db_type="file",
                    version=self.option("swissprot_version"))
        conn = sqlite3.connect(nracc2des)
        cursor = conn.cursor()

        xml = ET.parse(xml_path)
        root = xml.getroot()
        BlastOutput_iterations = root.find('BlastOutput_iterations')
        for one_query in BlastOutput_iterations.findall('Iteration'):
            iteration_hits = one_query.findall('Iteration_hits')
            for iteration_hit in iteration_hits:
                hits = iteration_hit.findall('Hit')
                for hit in hits:
                    hit_id = hit.find('Hit_id')
                    hit_def = hit.find('Hit_def')
                    # hit_def = hit.find('Hit_id')
                    # hit_id = hit.find('Hit_def')
                    hit_id_split = re.split(r'\s', hit_id.text, maxsplit=1)
                    
                    acc_id = hit_id_split[0]
                    if len(acc_id.split("|")) > 1 and self.option("database") != "swissprot":
                        gi_id = hit_id_split[0].split("|")[1]
                        acc_id = hit_id_split[0].split("|")[-2]
                    # try:
                    #     int(gi_id)
                    # except:
                    #     self.logger.info(hit_def)
                    # nracc2des = self.db_path + "/nr_acc2des.cpickle"
                    # with open (nracc2des, 'rb') as f:
                    #    acc2des = cpickle.load(f)
                    desc = ""
                    try:
                        cursor.execute('select * from acc2des where acc="{}"'.format(acc_id))
                        desc = cursor.fetchall()[0][1]
                        description = desc
                        hit_def.text = description
                    except:
                        hits.remove(hit)
                        self.logger.info("没找到acc_id:{}".format(acc_id))


        xml.write('tmp.txt')
        with open('tmp.txt', 'rb') as f, open('tmp.xml', 'wb') as w:
            lines = f.readlines()
            a = '<?xml version=\"1.0\"?>\n<!DOCTYPE BlastOutput PUBLIC \"-//NCBI//NCBI BlastOutput/EN\" \"http://www.ncbi.nlm.nih.gov/dtd/NCBI_BlastOutput.dtd\">\n'
            w.write(a)
            w.writelines(lines)
        os.remove('tmp.txt')
        shutil.move('tmp.xml', xml_path)

    def change_version(self, outputfile):
        path = outputfile
        with open(path,"r") as file:
            for line in file:
                line = line.strip()
                if line.lstrip().startswith("<Hit_id>"):
                    m = re.match("<Hit_id>(.+)</Hit_id>", line.lstrip())
                    if m:
                        self.ori.append(m.group(1))
                        line = file.next()
                        n = re.match("<Hit_def>(.+)</Hit_def>", line.lstrip())
                        try:
                            self.repl.append(n.group(1))
                        except:
                            print line
        with open(path,"r") as file, open(path + "_new", "w") as fw:
            i = 0
            for line in file:
                if line.lstrip().startswith("<BlastOutput_db>"):
                    line = line.replace("<BlastOutput_db>", "<BlastOutput_db>" + self.option("database"))
                if line.lstrip().startswith("<BlastOutput_version>"):
                    line = line.replace("diamond 0.8.35", "BLASTX 2.3.0+")
                '''
                # 新版diamond 不用替换id 和 description
                if line.lstrip().startswith("<Hit_id>"):
                    m = re.match("<Hit_id>(.+)</Hit_id>", line.lstrip())
                    if m:
                        line = line.replace(self.ori[i],self.repl[i])
                if line.lstrip().startswith("<Hit_def>"):
                    m = re.match("<Hit_def>(.+)</Hit_def>", line.lstrip())
                    if m:
                        line = line.replace(self.repl[i],self.ori[i])
                        i += 1
                '''
                fw.write(line)
        shutil.copy(path + "_new", path)
        self.option('outxml', path)
        db_name = self.option("database")

        if db_name in ["nr", "animal", "fungi", "metazoa", "plant", "protist", "viridiplantae", "vertebrates", "swissprot"]:
            self.get_nrxml_gi_description(path)
            self.option('outxml',path + "_new")
        self.end()

    def run_code(self, cmd_name, cmd, shell=False, memory_err_code=[1, -6]):
        if shell:
            cmd = self.config.SOFTWARE_DIR + '/' + cmd
        # diamond2 可能因申请不到内存报错
        command = self.add_command(cmd_name, cmd, shell=shell, ignore_error=True)
        command.run()
        self.wait()
        if command.return_code == 0:
            self.logger.info('succeed in running {}'.format(cmd_name))
        elif command.return_code in memory_err_code:
            self.logger.info('Failed to allocate sufficient memory. Please refer to the manual for instructions on memory usage.')
            self.add_state("memory_limit")
        elif command.return_code is None:
            self.logger.warn('fail to run {}, try again'.format(cmd_name))
            command.rerun()
            self.wait()
            if command.return_code is 0:
                self.logger.info('succeed in rerunning {}'.format(cmd_name))
            else:
                self.set_error('fail to rerun %s, abord', variables=(cmd_name), code="33700808")
        else:
            self.set_error('fail to run %s, abord', variables=(cmd_name), code="33700809")
