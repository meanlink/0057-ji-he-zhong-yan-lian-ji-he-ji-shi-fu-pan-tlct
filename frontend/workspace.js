import {mount} from './base.js';
import {render as roster} from './roster_page.js';
import {render as clock} from './clock_page.js';
import {render as tail} from './tail_page.js';
import {render as followup} from './followup_page.js';
const pages = {"roster": "演练名册", "clock": "观测计时", "tail": "集合时效", "followup": "漏记补查"};
const screens = {roster, clock, tail, followup};
mount({title: "集合钟 · 演练集合计时复盘", kicker: "松桥记录室 / 集合观察", pages, render: (page, outlet, user) => screens[page](outlet, user)});
