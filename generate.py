# coding: UTF-8

import sys
import math
import json
import codecs
import xml.dom.minidom
from pydub import AudioSegment

def calcTime(pos):
	bpm = bpmInfo["bpm"]
	preLength = bpmInfo["preLength"]
	return 60.0 / (bpm * 2) * (float(pos) + preLength)
	
def isGrayNote(pos):
	return '.' in pos

class NoteBase(object):
	def __init__(self, note, tp):
		self.line = int(note.getElementsByTagName('line{}'.format(tp))[0].childNodes[0].data) + 4
		self.pos = str(note.getElementsByTagName('pos{}'.format(tp))[0].childNodes[0].data)
		
	def generate(self, resultList, bpm):
		pass

# 单键，包括蓝键和灰键
# line: 1-7
# pos: 节拍数
class NoteN(NoteBase):
	def __init__(self, note, tp):
		super(NoteN, self).__init__(note, tp)
		self.isSkill = False
		
	def generate(self, resultList):
		resultList.append({
			"type": "Skill" if self.isSkill else ("SingleOff" if isGrayNote(self.pos) else "Single"),
			"lane": self.line,
			"time": calcTime(self.pos),
		})
		
	def setToSkill(self):
		self.isSkill = True

# 粉键
class NoteF(NoteBase):
	def __init__(self, note, tp):
		super(NoteF, self).__init__(note, tp)
		
	def generate(self, resultList):
		resultList.append({
			"type": "Flick",
			"lane": self.line,
			"time": calcTime(self.pos),
		})

# 滑条起点
# nextNote可以是LineMiddle，LineEndN和LineEndF
class LineStart(NoteBase):
	def __init__(self, note, tp):
		super(LineStart, self).__init__(note, tp)
		self.lineInsts = []
		self.nextNode = None
		self.prevNode = None
		self.isSkill = False
		
	def addLineInst(self, nodeInst):
		self.lineInsts.append(nodeInst)
		
	def sortLineInst(self):
		# 将后续节点排序：
		self.lineInsts.sort(key=lambda nodeInst: float(nodeInst.pos))
		curNode = self
		nextNode = self.lineInsts[0]
		for nodeInst in self.lineInsts:
			curNode.nextNode = nextNode
			nextNode.prevNode = curNode
			curNode, nextNode = nextNode, nodeInst
		curNode.nextNode = nextNode
		nextNode.prevNode = curNode
		
	def generate(self, resultList):
		resultList.append({
			"type": "Skill" if self.isSkill else "Long",
			"lane": self.line,
			"time": calcTime(self.pos),
		})
		resultList.append({
			"type": "Bar",
			"lane": [self.line, self.nextNode.line],
			"time": [calcTime(self.pos), calcTime(self.nextNode.pos)],
		})
		
	def setToSkill(self):
		self.isSkill = True

# 滑条中间节点
class LineMiddle(NoteBase):
	def __init__(self, note, tp):
		super(LineMiddle, self).__init__(note, tp)
		self.startLine = int(note.getElementsByTagName('startlineL'.format(tp))[0].childNodes[0].data) + 4
		self.startPos = str(note.getElementsByTagName('startposL'.format(tp))[0].childNodes[0].data)
		self.nextNode = None
		self.prevNode = None
		
	def generate(self, resultList):
		resultList.append({
			"type": "Tick",
			"lane": self.line,
			"time": calcTime(self.pos),
		})
		resultList.append({
			"type": "Bar",
			"lane": [self.line, self.nextNode.line],
			"time": [calcTime(self.pos), calcTime(self.nextNode.pos)],
		})

# 滑条终点N
class LineEndN(NoteBase):
	def __init__(self, note, tp):
		super(LineEndN, self).__init__(note, tp)
		self.startLine = int(note.getElementsByTagName('startlineL'.format(tp))[0].childNodes[0].data) + 4
		self.startPos = str(note.getElementsByTagName('startposL'.format(tp))[0].childNodes[0].data)
		self.nextNode = None
		self.prevNode = None
		
	def generate(self, resultList):
		resultList.append({
			"type": "Long",
			"lane": self.line,
			"time": calcTime(self.pos),
		})

# 滑条终点F
class LineEndF(NoteBase):
	def __init__(self, note, tp):
		super(LineEndF, self).__init__(note, tp)
		self.startLine = int(note.getElementsByTagName('startlineL'.format(tp))[0].childNodes[0].data) + 4
		self.startPos = str(note.getElementsByTagName('startposL'.format(tp))[0].childNodes[0].data)
		self.nextNode = None
		self.prevNode = None
		
	def generate(self, resultList):
		resultList.append({
			"type": "Flick",
			"lane": self.line,
			"time": calcTime(self.pos),
		})

nodeTypeClsDict = {
	"N": NoteN,
	"F": NoteF,
	"LS": LineStart,
	"LM": LineMiddle,
	"LE": LineEndN,
	"LF": LineEndF,
}

bpmInfo = {}

# 命令行参数：文件夹名称 是否导出歌曲信息 是否导出MP3
def process():
	directoryName = sys.argv[1]
	outputSongInfo = sys.argv[2] == "1"
	outputMP3 = sys.argv[2] == "1"
	configFilePath = "custom/{}/{}.json".format(directoryName, directoryName)
	config = None
	with codecs.open(configFilePath, 'r', 'utf-8') as configFile:
		config = json.load(configFile)
	
	if config is None:
		print "Cannot load config."
		return
		
	if not config.has_key("name") or not config.has_key("singer") or not config.has_key("difficulty"):
		print "Song meta info is not enough."
		return
		
	# 更改歌曲名称、歌手名称与难度：
	if outputSongInfo:
		with codecs.open("orig/all.5.json", 'r', 'utf-8') as songNames:
			songs = json.load(songNames)
			songs["1"]["bandId"] = 999
			songs["1"]["musicTitle"] = [config["name"]] * 4
			for index, difficulty in enumerate(config["difficulty"]):
				songs["1"]["difficulty"][str(index)]["playLevel"] = int(difficulty)
		
		with codecs.open("orig/all.1.json", 'r', 'utf-8') as singerNames:
			singers = json.load(singerNames)
			singers["999"] = {
				"bandName": [config["singer"]] * 4,
			}
		
		with codecs.open("all/all.5.json", "w", 'utf-8') as output:
			json.dump(songs, output, ensure_ascii=False)
			
		with codecs.open("all/all.1.json", "w", 'utf-8') as output:
			json.dump(singers, output, ensure_ascii=False)
		
	# 记录技能节点位置与fever位置：
	skills = []
	fevers = []
	for skill in config.get("skills", []):
		skillPos = str(skill[0])
		skillLine = skill[1]
		skills.append((skillPos, skillLine))
	for fever in config.get("fevers", []):
		fevers.append(str(fever))
	
	# 读取sav文件：
	document = xml.dom.minidom.parse("custom/{}/{}.sav".format(directoryName, directoryName))
	root = document.documentElement
	types = ["N", "L", "F"]

	noteMap = {}
	lineSList = []
	lineMEFList = []

	info = root.getElementsByTagName("info")[0]
	bpm = int(info.getElementsByTagName("bpm")[0].childNodes[0].data)
	bpmInfo["bpm"] = bpm
	delay = float(info.getElementsByTagName("delay")[0].childNodes[0].data)

	for tp in types:
		nodeList = root.getElementsByTagName("note{}".format(tp))
		for note in nodeList:
			nodeType = note.getElementsByTagName('type{}'.format(tp))[0].childNodes[0].data
			nodeInst = nodeTypeClsDict[nodeType](note, tp)
			# 加入noteMap：
			noteMap.setdefault(nodeInst.pos, {})
			noteMap[nodeInst.pos][nodeInst.line] = nodeInst
			# 记录绿条中间节点与结束节点：
			if nodeType in ["LM", "LE", "LF"]:
				lineMEFList.append(nodeInst)
			elif nodeType == "LS":
				lineSList.append(nodeInst)
			
	# 关联绿条：
	for nodeInst in lineMEFList:
		startLine = nodeInst.startLine
		startPos = nodeInst.startPos
		startInst = noteMap[startPos][startLine]
		startInst.addLineInst(nodeInst)
	for nodeInst in lineSList:
		nodeInst.sortLineInst()

	# 添加skill节点：
	for skillPos, skillLine in skills:
		noteInst = noteMap.get(skillPos, {}).get(skillLine)
		if noteInst is None:
			print "No note at {}, {}".format(skillPos, skillLine)
		elif noteInst.__class__.__name__ not in ["LineStart", "NoteN"]:
			print "Cannot change {} note to skill note.".format(noteInst.__class__.__name__)
		else:
			noteInst.setToSkill()
			
	# 添加fever信息：
	for index, fever in enumerate(fevers):
		if index == 0:
			flag = "FeverReady"
		elif index == 1:
			flag = "FeverStart"
		else:
			flag = "FeverEnd"
		noteMap.setdefault(fever, {})
		noteMap[fever][-1] = flag
	
	# 计算要添加多长时间的空白：
	preLength = 0
	length = 0
	valid = False
	if config.has_key("preLength"):
		preLength = config["preLength"]
		length = 60.0 / (bpm * 2) * (preLength - 1) # 虽然不知道为什么，但是这里好像要减去1/8拍？暂时存疑，看看这个方法是不是每首歌都适用。
		if length >= delay:
			valid = True
	
	if not valid:
		# 需要自动算出preLength：
		preLengthFloat = delay / (60.0 / (bpm * 2)) / 8
		preLengthFloat = math.ceil(preLengthFloat)
		preLength = int(preLengthFloat) * 8
		length = 60.0 / (bpm * 2) * (preLength - 1) # 虽然不知道为什么，但是这里好像要减去1/8拍？暂时存疑，看看这个方法是不是每首歌都适用。
		
	bpmInfo["preLength"] = preLength
	
	# 打开MP3文件，生成新的MP3文件：
	if outputMP3:
		music = AudioSegment.from_file("custom/{}/{}.mp3".format(directoryName, directoryName))
		blank = AudioSegment.silent(duration=int((length - delay) * 1000))
		resMusic = blank + music
		resMusic.export("music/{}".format(config.get("outputMP3", "bgm001.mp3")), format="mp3")

	#开始生成json：
	resultListMap = []
	resultListMap.append({
		"type": "BPM",
		"bpm": bpm,
		"time": 0,
	})
	resultListSimulator = []
	times = noteMap.keys()
	times.sort(key=lambda item: float(item))
	
	for tm in times:
		notes = noteMap[tm]
		# fever标记：
		if notes.has_key(-1):
			flag = notes[-1]
			resultListMap.append({
				"type": flag,
				"time": calcTime(tm),
			})
			notes.pop(-1)
		# 其余note输出：
		noteList = notes.values()
		hasSim = len(noteList) == 2
		for note in noteList:
			note.generate(resultListMap)
			note.generate(resultListSimulator)
			if note.__class__.__name__ == "LineMiddle":
				hasSim = False
		# 是否有同时点击线
		if hasSim:
			simDict = {
				"type": "Sim",
				"lane": [noteList[0].line, noteList[1].line],
				"time": calcTime(tm),
			}		
			resultListMap.append(simDict)
			resultListSimulator.append(simDict)
	
	with open("graphics/simulator/{}".format(config.get("outputJson", "1.expert.json")), "wt") as output:
		json.dump(resultListSimulator, output)
	with open("graphics/chart/{}".format(config.get("outputJson", "1.expert.json")), "wt") as output:
		json.dump(resultListMap, output)

if __name__ == "__main__":
	process()