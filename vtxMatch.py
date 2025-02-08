#!/usr/bin/env python
'''
Match postion and normal vertex from act vertex to ref vertex.
Need numpy
Usage:
import vtxMatch
from importlib import reload
reload(vtxMatch)

'''
import maya.cmds as cmds
import sys
try:
    import numpy
except ImportError:
    sys.exit("This script requires the numpy module")


__author__ = "Jiapei Lu"
__email__ = "aurora.lu@gmail.com"
__version__ = "1.0.3"


class PostionMatcher():
    def __init__(self):
        self.aVtxList = []
        self.bVtxList = []
        self.aVtxDic = {}
        self.bVtxDic = {}

    def updated_xform(self):
        for vtx in self.aVtxList:
            # vtx_t =  cmds.xform(  vtx, q = True, ws = True, t = True )
            self.aVtxDic[vtx] = cmds.xform(vtx, q=True, ws=True, t=True)
        for vtx in self.bVtxList:
            # vtx_t =  cmds.xform(  vtx, q = True, ws = True, t = True )
            self.bVtxDic[vtx] = cmds.xform(vtx, q=True, ws=True, t=True)


lPostionMatcher = PostionMatcher()


def getRefVertex(*args):
    lPostionMatcher.bVtxList = cmds.ls(sl=True, fl=True)  # act vtxs
    print("Source Vertexs:", len(lPostionMatcher.bVtxList))


def getActVerex(*args):
    lPostionMatcher.aVtxList = cmds.ls(sl=True, fl=True)  # act vtxs
    print("Target Vertexs:", len(lPostionMatcher.aVtxList))


def parent_constraint_closer_items(*args):
    for objA, objB in pair_by_distance(lPostionMatcher):
        print(objA, objB)
        # cmds.xform( objA, a = True, ws = True, t = lPostionMatcher.bVtxDic[objB] )
        cmds.parentConstraint(objB, objA, mo=True)


def pair_by_distance(vList: PostionMatcher):
    vList.updated_xform()
    distanceRange = cmds.floatField(Threshold, q=True, v=True)
    for objA in list(vList.aVtxDic.keys()):
        distanctCompare = {}
        for objB in list(vList.bVtxDic.keys()):
            a = numpy.array(vList.aVtxDic[objA])
            b = numpy.array(vList.bVtxDic[objB])
            dis = numpy.linalg.norm(a - b)
            if dis < distanceRange:
                distanctCompare[objB] = dis
                if len(list(distanctCompare.keys())) > 1:
                    objB = sorted(distanctCompare, key=distanctCompare.get)[0]
                yield objA,   objB


def matchVertexs(*args):
    for objA,   objB in pair_by_distance(lPostionMatcher):
        cmds.xform(objA, a=True, ws=True, t=lPostionMatcher.bVtxDic[objB])
        if cmds.checkBox(normal, q=True, v=True):
            bNormal = cmds.polyNormalPerVertex(objB, query=True, xyz=True)
            cmds.polyNormalPerVertex(objA, xyz=(
                bNormal[0], bNormal[1], bNormal[2]))
        print('=== Match Vertex Done ===')


wd_Match_Vertexs = 'Match_Vertexs'
if cmds.window(wd_Match_Vertexs, q=True, ex=True):
    cmds.deleteUI(wd_Match_Vertexs)

wd_Match_Vertexs = cmds.window(wd_Match_Vertexs, title='Match Vertexs')
cmds.columnLayout(adjustableColumn=True, rs=5, cw=160)
cmds.button(label="Get Source Objects", command=getRefVertex)
cmds.button(label="Get Target Objects", command=getActVerex)
cmds.rowLayout(h=22, numberOfColumns=2, columnWidth2=(80, 75), adjustableColumn=True,
               columnAlign=(1, 'left'), columnAttach=[(1, 'both', 0), (2, 'both', 0)])
cmds.text(l='Threshold:', al='right')
Threshold = cmds.floatField(minValue=0, maxValue=10, value=1, step=0.1, pre=1)
cmds.setParent('..')
normal = cmds.checkBox(label='Copy Vertex Normal', v=True)
cmds.button(label="Match Vertexs", command=matchVertexs)

cmds.showWindow(wd_Match_Vertexs)
