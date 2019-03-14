# -*- coding：utf-8 -*-
import os
import re
import requests
import bs4
import sys
import webbrowser
import math
import pymysql
import jieba
import pandas as pd
import matplotlib as mpl
mpl.use('TkAgg')
import matplotlib.pyplot as plt

from time import sleep
from urllib import (request, error, parse)
from threading import Thread
from wordcloud import WordCloud, STOPWORDS, ImageColorGenerator

headers = {
        'Host': 'hr.tencent.com',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'}

class TencentJob(object):
    def __init__(self):
        self.url_base = 'https://hr.tencent.com/position.php?'
        self.conn = pymysql.connect(
            host='xxx.xxx.xxx.xxx', user='root', password='xxxxxx', charset='utf8')
        self.cur=self.conn.cursor()
        self.cur.execute('use job')
        self.values = {}
        self.html_pool = []
        self.job_pool = []

    # 过滤字符串只保留中文
    def translate(self,str):
        line = str.strip()
        p2 = re.compile('[^\u4e00-\u9fa5]')  # 中文的编码范围是：\u4e00到\u9fa5
        zh = " ".join(p2.split(line)).strip()
        zh = ",".join(zh.split())
        str = re.sub("[A-Za-z0-9!！，%\[\],。]", "", zh)
        return str

    def word_cloud(self,csv_file, stopwords_path, pic_path):
        pic_name = csv_file+"_词云图.png"
        path = os.path.abspath(os.curdir)
        csv_file = path + "/" + csv_file + ".csv"
        # csv_file = csv_file.replace('\\', '\\\\')
        d = pd.read_csv(csv_file, engine='python', encoding='utf-8')
        content = []
        for i in d['names']:
            try:
                i = self.translate(i)
            except AttributeError as e:
                continue
            else:
                content.append(i)
        comment_after_split = jieba.cut(str(content), cut_all=False)
        wl_space_split = " ".join(comment_after_split)
        backgroud_Image = plt.imread(pic_path)
        stopwords = STOPWORDS.copy()
        with open(stopwords_path, 'r', encoding='utf-8') as f:
            for i in f.readlines():
                stopwords.add(i.strip('\n'))
            f.close()

        wc = WordCloud(width=1024, height=768, background_color='white',
                    mask=backgroud_Image, font_path="font_type/SimHei.ttf",
                    stopwords=stopwords, max_font_size=400,
                    random_state=50)
        wc.generate_from_text(wl_space_split)
        img_colors = ImageColorGenerator(backgroud_Image)
        wc.recolor(color_func=img_colors)
        plt.imshow(wc)
        plt.axis('off')
        plt.show()
        wc.to_file(pic_name)

    def draw_word_cloud(self):
        self.word_cloud("tencentJob", "stopwords.txt", "ttt.jpg")

    def store_job(self):
        for elem in self.job_pool:
            self.cur.execute("insert into tencent (name,type,num,publish,location)" 
                             "values('{}','{}','{}','{}','{}')"
                             .format(str(elem['name']), str(elem['type']), str(elem['num']), str(elem['publish']), str(elem['location'])))
            self.conn.commit()

    def store_job_to_csv(self):
        name_list = []
        type_list = []
        num_list = []
        publish_list = []
        location_list = []
        for elem in self.job_pool:
            name_list.append(str(elem['name']))
            type_list.append(str(elem['type']))
            num_list.append(str(elem['num']))
            publish_list.append(str(elem['publish']))
            location_list.append(str(elem['location']))
        infos = {'name': name_list, 'type': type_list,
                 'num': num_list, 'publish': publish_list,'location':location_list}
        print(infos)
        data = pd.DataFrame(
            data=infos, columns=['name', 'type', 'num', 'publish', 'location'])
        print(data)
        data.to_csv("hr_tencent/tencentJob.csv")
            
    
    def parse_job_html(self,html_decode):
        pass

    def crawl_job_html(self, url_crawl):
        try:
            response = request.Request(url_crawl, headers=headers)
            html_requested = request.urlopen(response)
            html_decoded = html_requested.read().decode('utf-8')
            self.html_pool.append(html_decoded)
            sleep(3)
        except error.HTTPError as e:
            if hasattr(e, 'code'):
                print(e.code)

    def get_job_html(self):
        html_thread_object = []
        for job in self.job_pool:
            # 创建新线程
            t = Thread(target=self.crawl_job_html, args=(
                job['href'],), name='Crawl_Thread_Html')
            html_thread_object.append(t)
        # 启动线程
        for elem in html_thread_object:
            elem.start()
        # 等待结束 
        for elem in html_thread_object:
            elem.join()


    def parse_job_link(self, html_docoded):
        job_dict = {}
        soup=bs4.BeautifulSoup(html_docoded,'lxml')
        # job_thread_object = []
        for job in soup.select('td.square a'):
            job_dict['href'] = job['href']
            job_dict['name'] = job.get_text()
            for td in job.find_parents('td'):
                job_dict['type']=td.find_next_siblings('td')[0].get_text()
                job_dict['num']=td.find_next_siblings('td')[1].get_text()
                job_dict['location'] = td.find_next_siblings('td')[2].get_text()
                job_dict['publish'] = td.find_next_siblings('td')[3].get_text()
            # t = Thread(target=self.crawl_job_des, args=(
            #         crawler_url,), name='Crawl_Thread')
            # job_thread_object.append(t)
            self.job_pool.append(job_dict)
        
    def crawl_job_link(self, url_crawl):
        try:
            response = request.Request(url_crawl, headers=headers)
            html_requested = request.urlopen(response)
            html_decoded = html_requested.read().decode('utf-8')
            self.parse_job_link(html_decoded)
            sleep(3)
        except error.HTTPError as e:
            if hasattr(e, 'code'):
                print(e.code)

    def get_job_link(self,url):
        page_url_list = []
        link_thread_object = []
        response = request.Request(url, headers=headers)
        html_requested = request.urlopen(response)
        html_decoded = html_requested.read().decode('utf-8')
        # 获取多少页
        soup = bs4.BeautifulSoup(html_decoded, 'lxml')
        # 先获取一共有多少条数据
        total_num = int(soup.select(".tablelist .total")[0].get_text())
        for x in range(0, math.ceil(total_num/10)):
            self.values['start'] = x*10
            data = parse.urlencode(self.values)
            crawler_url = self.url_base+data
            print(crawler_url)
            # 创建新线程
            t = Thread(target=self.crawl_job_link, args=(
                crawler_url,), name='Crawl_Thread')
            link_thread_object.append(t)
        # 启动线程
        for elem in link_thread_object:
            elem.start()
        # 等待结束
        for elem in link_thread_object:
            elem.join()

    def run(self):
        # values['keywords'] = input('请输入工作关键词：\n')
        self.values['keywords'] = '云'
        self.values['tid'] = '87'
        self.values['lid'] = '2156'
        data = parse.urlencode(self.values)
        url = self.url_base+data
        self.get_job_link(url)
        # 将数据存到mysql
        # self.store_job()
        # 将数据存到csv
        self.store_job_to_csv()
        
if __name__ == "__main__":
    tJob=TencentJob()
    # tJob.run()
    tJob.draw_word_cloud()
