# -*- coding: utf8 -*-
'''
Created on 2010-9-28

@author: chinple
'''
import os
import time
import re
from libs.reg import PyRegExp
from libs.objop import ObjOperation
from libs.tvg import TValueGroup
from libs.ini import IniConfigure
from tmodel.model.logxml import TestLoggerFactory, TestLogger
from libs.syslog import logManager, slog

class MTConst:
    beginTestCaseInfo = "\t%s Running ..."
    endTestCaseInfo = "%s:\t%s"

    equalInfo = "Assert %sEqual, in fact %sEqual: Expected \"%s\", Actual \"%s\" for \"%s\""
    conditionInfo = "Assert %s, in fact %s for %s"
    containInfo = "Contains %s for %s: %s should be contained in: %s"
    jsonContainInfo = "JSON %scontained, for %s:\n%s"

    sysFunReg = PyRegExp('__.+__|BeginTestCase|EndTestCase|SetUp|TearDown|Property|Assert|Logger')
    exceptReg = PyRegExp(".*driver[a-z|A-Z|]*.py|.*casemodel[a-z|A-Z|]*.py")

    passed = 0
    warned = 1
    failed = 2
    notRun = 3

class TestCheck(Exception):
    pass

class TestAssert(object):
    def __init__(self, tlog):
        self.isWarned = False
        self.tlog = tlog

    def assumeEqual(self, expectedValue, actualValue, msg):            
        if expectedValue != actualValue:
            self.tlog.warn(MTConst.equalInfo % ("", "NOT ", expectedValue, actualValue, msg))
            self.isWarned = True
        else:
            self.tlog.success(MTConst.equalInfo % ("", "", expectedValue, actualValue, msg))

    def assumeTrue(self, condition, msg):            
        if not condition:
            self.tlog.warn(MTConst.conditionInfo % ("True", "False", msg))
            self.isWarned = True
        else:
            self.tlog.success(MTConst.conditionInfo % ("True", "True", msg))

    # precondition or condition Checker
    def areEqual(self, expectedValue, actualValue, msg):
        if expectedValue != actualValue:
            raise TestCheck(MTConst.equalInfo % ("", "NOT ", expectedValue, actualValue, msg))
        self.tlog.success(MTConst.equalInfo % ("", "", expectedValue, actualValue, msg))

    def areNotEqual(self, expectedValue, actualValue, msg):
        if expectedValue == actualValue:
            raise TestCheck(MTConst.equalInfo % ("Not ", "", expectedValue, actualValue, msg))
        self.tlog.success(MTConst.equalInfo % ("NOT ", "Not ", expectedValue, actualValue, msg))

    
    def isTrue(self, condition, msg):
        if not condition:
            raise TestCheck(MTConst.conditionInfo % ("True", "False", msg))
        self.tlog.success(MTConst.conditionInfo % ("True", "True", msg))

    def isContained(self, strA, inStrB, msg):
        if strA != None and (inStrB == None or not inStrB.__contains__(strA)):
            raise TestCheck(MTConst.ContainInfo % ("False", msg, strA, inStrB))
        self.tlog.success(MTConst.ContainInfo % ("True", msg, strA, inStrB))

    def jsonEqual(self, expectedValue, actualValue, msg, isAddEqInfo=False, ignoreKey=None):
        if ignoreKey is None:
            cmpRes, cmpInfo = ObjOperation.jsonEqual(expectedValue, actualValue, isAddEqInfo)
        else:
            def isCmp(key, keyPath):
                return not ignoreKey.__contains__(key)
            cmpRes, cmpInfo = ObjOperation.jsonEqual(expectedValue, actualValue, isAddEqInfo, isCmpHandler=isCmp)
        if cmpRes % 1000 != 0:
            raise TestCheck(MTConst.jsonContainInfo % ("NOT ", msg, cmpInfo))
        self.tlog.success(MTConst.jsonContainInfo % ("", msg, cmpInfo))

    def captureIfAreEqual(self, expectedValue, actualValue, funPoint): 
        self.areEqual(expectedValue, actualValue, funPoint)

class TestCaseFactory:

    def __init__(self):
        self.runModeEnum = {'slook':-22, 'scenario':-21, 'param':-11, 'look':-10, 'show':-9, 'debug':0, 'run':9, 'rerun':10, 'stop':-9}
        self.testResInfo = ['Passed', 'Warned', 'Failed', 'NotRun']
        self.tlog = TestLoggerFactory()
        self.tprop = IniConfigure("mtest.ini")
        self.tassert = TestAssert(self.tlog)
        self.tcInfos = TValueGroup({})
        self.init()
        
    def init(self, runMode='debug', tcPattern=None, outTcPattern=None, searchKey=None,
             logFilePath=None):
        try:
            self.runMode = self.runModeEnum[runMode]
        except:
            self.runMode = self.runModeEnum['debug']
        self.searchKey = searchKey
        self.tcReg = PyRegExp(tcPattern) if tcPattern != None and tcPattern != "" else None
        self.tcRegOutScope = PyRegExp(outTcPattern) if outTcPattern != None and outTcPattern != "" else None
        self.isModeling = False

        logManager.removeHandler(slog, 1)
        logManager.addFileHandler(slog, None, "mtest.log")  # set syslog for test

        if str(logFilePath).strip().endswith(".html"):
            from tmodel.model.logreport import HtmlTestReport
            self.tlog.registerLogger(HtmlTestReport, logFilePath, False)
            self.tlog.registerLogger(TestLogger, "testlog.log")
        else:
            self.tlog.registerLogger(TestLogger, logFilePath)

    def addRunMode(self, modeName, mode):
        self.runModeEnum[modeName] = mode

    def __checkSignal(self):
        if os.path.exists("stop.signal"):
            self.runMode = self.runModeEnum['stop']
        else:
            while os.path.exists("pause.signal"):
                time.sleep(30)
                slog.info(".")

    def isInMode(self, modeName, modeType=0, isCheckSignal=False):
        if isCheckSignal and self.runMode >= self.runModeEnum['debug']:
            self.__checkSignal()
        try:
            modeCmp = self.runMode - self.runModeEnum[modeName]
            if modeType > 0:
                return modeCmp >= 0
            elif modeType == 0:
                return modeCmp == 0
            else:
                return modeCmp <= 0
        except:
            return False

    def isInScope(self, csName, searchKeys=None):
        if self.searchKey != None and self.searchKey != "":
            if searchKeys == None:
                return False
            isNotMatch = True
            for searchVal in searchKeys.values():
                if re.match(self.searchKey, searchVal) != None:
                    isNotMatch = False
                    break
            if isNotMatch:
                return False
        return (self.tcReg == None or self.tcReg.isMatch(csName)) and \
            (self.tcRegOutScope == None or not self.tcRegOutScope.isMatch(csName))

    def addResultType(self, resType, resInfo):
        while resType > 3:
            try:
                self.testResInfo[resType] = resInfo
                break
            except:
                self.testResInfo.append(None)

    def getResInfo(self, resType):
        return self.testResInfo[resType]

    def getTCInfo(self, tcName):
        if not self.tcInfos.keys().__contains__(tcName):
            tcInfo = TValueGroup({})
            tcInfo.Orders = None
            tcInfo.isTested = False
            self.tcInfos[tcName] = tcInfo
        return self.tcInfos[tcName]

    def getTCDespcription(self, sparam, despFormat):
        if despFormat == "" or despFormat == None:
            if sparam.paramName == None:
                desp = ""
            else:
                desp = "(%s%s:%s)" % (("[%s]" % sparam.orderNum)if sparam.orderNum > 0 else "",
                    sparam.paramName, sparam[sparam.paramName])
        else:
            desp = despFormat
            for skey in sparam.keys():
                stype = sparam.GetType(skey)
                if stype == None:
                    stype = str(sparam[skey])[0:26]
                desp = desp.replace("{%s}" % skey, stype)
        return desp

    def getTCFullName(self, tcName, pIndex, desp):
        return "%s%s %s" % (tcName, pIndex if pIndex > 0 else "", desp)

    def getRunInfo(self, tcName, tempObj):
        tcInfo = self.getTCInfo(tcName)
        runList = []
        if not tcInfo.isTested or self.runMode == 10:
            filteredList = []
            for caseName in tcInfo.keys():
                caseFun = eval("tempObj.%s" % caseName)
                if not hasattr(caseFun, '__name__') or 'ScenarioDecorator' != caseFun.__name__ :
                    filteredList.append(caseName)
            for fName in filteredList:
                tcInfo.__delitem__(fName)
            runList = tcInfo.keys()

        if tcInfo.Orders != None:
            tOrders = type(tcInfo.Orders)
            if tOrders == bool:
                runList = list(runList)
                runList.sort(reverse=not tcInfo.Orders)
            if tOrders == list and len(tcInfo.Orders) > 0 and len(runList) > 1:
                runList = list(runList)
                orderList = []
                for caseName in tcInfo.Orders:
                    if runList.__contains__(caseName):
                        orderList.append(caseName)
                        runList.remove(caseName)
                runList = orderList + runList
        return (tcInfo, runList)

    def report(self, repHandler=slog.info, sumTitle='Test Summary:'):
        repRes = self.reportResult()
        if self.isInMode('show') or self.isInMode('scenario'):
            repHandler('\r\nFind Test Case(%s of %s):', repRes[MTConst.passed], repRes['num'])
            self.reportResult(MTConst.passed, repHandler)
            repHandler('Summary: %s of %s', repRes[MTConst.passed], repRes['num'])
        else:
            repHandler('\r\n%s\r\n%s' % (sumTitle, '-' * 60))
            sumInfo = '\r\nTotal\t%s, %sm:\r\n\t' % (repRes['num'], int(repRes['time'] / 60 + 0.5))
            hasRunRes = False
            for resType in range(4):
                try:
                    resInfo = self.getResInfo(resType)
                    resNum = ObjOperation.tryGetVal(repRes, resType, 0)
                    if resType != MTConst.notRun:
                        repHandler('%s\t%s:', resInfo, resNum)
                        self.reportResult(resType, repHandler)
                    sumInfo += (" + %s: %s" if hasRunRes else "%s: %s") % (resInfo, resNum)
                    hasRunRes = True
                except Exception as ex:
                    slog.warn(ex)
                    continue
            repHandler(sumInfo)
#            repHandler('\r\nLog File:\r\n\t%s\n\n' % self.tlog.GetLoggerPath())
        return repRes

    def reportResult(self, resType=None, repHandler=slog.info):
        runRep = {'num':0, 'time':0, MTConst.passed:0, MTConst.warned:0, MTConst.failed:0, MTConst.notRun:0}
        for tsName in self.tcInfos.keys():
            tcInfo = self.getTCInfo(tsName)
            for tcName in tcInfo.keys():
                tcResMap = tcInfo[tcName]
                for tpIndex in tcResMap.keys():
                    tcResInfo = tcResMap[tpIndex]
                    tcRes = tcResInfo['r']
                    tcTime = tcResInfo['t']
                    runRep[tcRes] = ObjOperation.tryGetVal(runRep, tcRes, 0) + 1
                    runRep['num'] += 1
                    runRep['time'] += tcTime
                    if resType == tcRes:
                        repHandler("\t%s%s", self.getTCFullName(tcName, tpIndex, tcResInfo['d']) , ("\t%ss" % tcTime) if tcTime > 0 else "")
        return runRep
