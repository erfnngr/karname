"""Five supported themes: default, three distinct refined references, plus Bento Grid."""
THEMES=[
 ('default','پیش‌فرض کارنامه','light'),
 ('emerald_ivory','زمرد و عاج','light'),
 ('glass_mist','مه شیشه‌ای ماه','light'),
 ('violet_modular','آبی ماژولار','light'),
 ('bento_grid','بنتو گرید','light'),
]
PALETTES={
 'emerald_ivory':(
  dict(bg='#F6F4EC',panel='#FCFBF7',text='#13261F',muted='#4B6359',border='#DEDCD0',field='#FAF9F3',button='#ECEBE2',hover='#DCE6DD',accent='#0F5B42',selected='#D8EAE0',today='#D5EBDD',danger='#9E233C',warning='#7D3F00',nav='#0A3828'),
  dict(bg='#0E2019',panel='#162F25',text='#F2FBF6',muted='#B4CCC0',border='#426353',field='#1F3E31',button='#264739',hover='#325A48',accent='#6BE0AC',selected='#265945',today='#1B4635',danger='#FFBBC3',warning='#FFD5AC',nav='#081A13')),
 'glass_mist':(
  dict(bg='#E9F1FA',panel='#F7FBFF',text='#102A43',muted='#486581',border='#C9DCF0',field='#FCFEFF',button='#E1EFFA',hover='#CFE4F7',accent='#0277BD',selected='#CFE8FA',today='#D5EEFA',danger='#A12745',warning='#824100',nav='#DFECFA'),
  dict(bg='#0A1624',panel='#13263B',text='#EFF7FF',muted='#ADC5DC',border='#3D5B78',field='#1A324B',button='#233E5A',hover='#2F4E6E',accent='#67C4FA',selected='#224B6E',today='#183D5B',danger='#FFB8C8',warning='#FFDAAE',nav='#0E1E30')),
 'violet_modular':(
  dict(bg='#EEF1F7',panel='#FFFFFF',text='#171E36',muted='#4C5675',border='#CFD7E7',field='#F8F9FD',button='#E4E8F3',hover='#D5DCF0',accent='#2B4ACB',selected='#DCE2FA',today='#D7E0FB',danger='#A12745',warning='#824100',nav='#FFFFFF'),
  dict(bg='#111626',panel='#1A2138',text='#F2F5FF',muted='#B5BEDB',border='#465278',field='#212A45',button='#2A3454',hover='#37446B',accent='#8DA6FF',selected='#2C3E73',today='#243463',danger='#FFB8C8',warning='#FFDAAE',nav='#161C30')),
 'bento_grid':(
  dict(bg='#EAF6FA',panel='#F7FCFE',text='#0F2937',muted='#466677',border='#C4E1EB',field='#FFFFFF',button='#DDF0F6',hover='#CCE7F0',accent='#0C8574',selected='#CFF2EC',today='#D6F0FB',danger='#A12745',warning='#824100',nav='#E3F3F8'),
  dict(bg='#0B1D29',panel='#132B3A',text='#EDF9FC',muted='#A8CAD9',border='#386075',field='#193546',button='#1F3F52',hover='#2A5269',accent='#5CE0C8',selected='#184E4B',today='#154354',danger='#FFB8C8',warning='#FFDAAE',nav='#0F2432')),
}
def preset(value):
    return value if value in {key for key,_,_ in THEMES} else 'default'
