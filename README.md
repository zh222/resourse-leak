使用 genymotion 中的 Google Pixel 模拟器，安卓版本 11.0；
先做单智能体强化学习的实验，所有配置都可以在 main.py 中修改，主要有：
* 算法导向：这里我暂时用 java heap, native heap, cpu, rss, activity coverage, random 这几种导向
* 待测 app：我根据代码行数对 app 进行了分类，在文件夹 apk 中，低于 1W 行的为 low，大于 1W 小于 5W 行的为 middle，大于 5W 行的为 high；暂时各找了 5 个左右（但由于 genymotion 只支持 x86，可能有些没办法安装，后面还要继续加）。
* ports：这个是 appium 与各个模拟器的通信端口，暂不考虑，等开始做多智能体的时候会用到。
  
我这边先做一下 high 规模的 app
