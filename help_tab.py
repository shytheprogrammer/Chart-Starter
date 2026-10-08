"""Searchable, read-only Help tab, with keyboard-copyable instructions."""
import tkinter as tk
from tkinter import ttk
from help_content import TOPICS

class HelpTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=16)
        ttk.Label(self, text='Chart Starter 1.0 • Help', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(self, text='Select a topic or search for a feature. Instructions can be selected and copied.').pack(anchor='w', pady=(2,12))
        search_row = ttk.Frame(self); search_row.pack(fill='x')
        ttk.Label(search_row, text='Search help').pack(side='left')
        self.query = tk.StringVar()
        ttk.Entry(search_row, textvariable=self.query).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(search_row, text='Clear', command=lambda: self.query.set('')).pack(side='left')
        panes = ttk.Panedwindow(self, orient='horizontal'); panes.pack(fill='both', expand=True, pady=(12,0))
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=1); panes.add(right, weight=4)
        self.topics = tk.Listbox(left, font=('Segoe UI',10), exportselection=False, width=33, activestyle='none', selectbackground='#2563eb', relief='flat')
        self.topics.pack(side='left',fill='both',expand=True)
        topic_scroll=ttk.Scrollbar(left,command=self.topics.yview);topic_scroll.pack(side='right',fill='y')
        self.topics.configure(yscrollcommand=topic_scroll.set)
        self.text = tk.Text(right, wrap='word', font=('Segoe UI',11), padx=16, pady=12, relief='flat', background='#ffffff', foreground='#22324a')
        self.text.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(right,command=self.text.yview);scroll.pack(side='right',fill='y');self.text.configure(yscrollcommand=scroll.set)
        self.text.tag_configure('title',font=('Segoe UI',17,'bold'),spacing3=12)
        self.text.tag_configure('match',background='#fff2ad')
        self.topics.bind('<<ListboxSelect>>',self.show_selected)
        self.query.trace_add('write',lambda *_:self.filter_topics())
        self.filter_topics()

    def filter_topics(self):
        query=self.query.get().strip().casefold()
        self.visible=[title for title,body in TOPICS.items() if not query or query in (title+' '+body).casefold()]
        self.topics.delete(0,'end')
        for title in self.visible:self.topics.insert('end',title)
        if self.visible:
            self.topics.selection_set(0);self.show_selected()
        else:self.show_text('No matching topic','Try a shorter search or clear the search field.')

    def show_selected(self,_=None):
        selection=self.topics.curselection()
        if selection:
            title=self.visible[selection[0]];self.show_text(title,TOPICS[title])

    def show_text(self,title,body):
        self.text.configure(state='normal');self.text.delete('1.0','end')
        self.text.insert('end',title+'\n','title');self.text.insert('end',body+'\n')
        query=self.query.get().strip()
        if query:
            start='1.0'
            while True:
                found=self.text.search(query,start,stopindex='end',nocase=True)
                if not found:break
                end=f'{found}+{len(query)}c';self.text.tag_add('match',found,end);start=end
        self.text.configure(state='disabled');self.text.yview_moveto(0)
