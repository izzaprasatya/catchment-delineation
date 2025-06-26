"""
Model exported as python.
Name : Catchment Delineation
Group : 
With QGIS : 34007
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterPoint
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterVectorDestination
from qgis.core import QgsProcessingParameterRasterDestination
from qgis.core import QgsProcessingParameterFeatureSink
import processing


class CatchmentDelineation(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer('dem', 'DEM', defaultValue=None))
        self.addParameter(QgsProcessingParameterPoint('outlet_coordinate_xy', 'Outlet Coordinate (x,y)', defaultValue=None))
        self.addParameter(QgsProcessingParameterNumber('stream_threshold', 'Stream Threshold', type=QgsProcessingParameterNumber.Integer, defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorDestination('CatchmentArea', 'Catchment Area', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterDestination('FlowAccumulation', 'Flow Accumulation', optional=True, createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterDestination('FlowDirection', 'Flow Direction', optional=True, createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('StreamNetwork', 'Stream Network', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(7, model_feedback)
        results = {}
        outputs = {}

        # r.watershed
        alg_params = {
            '-4': False,
            '-a': False,
            '-b': True,
            '-m': False,
            '-s': True,
            'GRASS_RASTER_FORMAT_META': None,
            'GRASS_RASTER_FORMAT_OPT': None,
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
            'GRASS_REGION_PARAMETER': None,
            'blocking': None,
            'convergence': 5,
            'depression': None,
            'disturbed_land': None,
            'elevation': parameters['dem'],
            'flow': None,
            'max_slope_length': None,
            'memory': 300,
            'threshold': None,
            'accumulation': parameters['FlowAccumulation'],
            'drainage': parameters['FlowDirection']
        }
        outputs['Rwatershed'] = processing.run('grass:r.watershed', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['FlowAccumulation'] = outputs['Rwatershed']['accumulation']
        results['FlowDirection'] = outputs['Rwatershed']['drainage']

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # r.water.outlet
        alg_params = {
            'GRASS_RASTER_FORMAT_META': None,
            'GRASS_RASTER_FORMAT_OPT': None,
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
            'GRASS_REGION_PARAMETER': None,
            'coordinates': parameters['outlet_coordinate_xy'],
            'input': outputs['Rwatershed']['drainage'],
            'output': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Rwateroutlet'] = processing.run('grass:r.water.outlet', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # r.stream.extract
        alg_params = {
            'GRASS_OUTPUT_TYPE_PARAMETER': 0,  # auto
            'GRASS_RASTER_FORMAT_META': None,
            'GRASS_RASTER_FORMAT_OPT': None,
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
            'GRASS_REGION_PARAMETER': None,
            'GRASS_VECTOR_DSCO': None,
            'GRASS_VECTOR_EXPORT_NOCAT': False,
            'GRASS_VECTOR_LCO': None,
            'accumulation': outputs['Rwatershed']['accumulation'],
            'd8cut': None,
            'depression': None,
            'elevation': parameters['dem'],
            'memory': 300,
            'mexp': 0,
            'stream_length': 0,
            'threshold': parameters['stream_threshold'],
            'stream_raster': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Rstreamextract'] = processing.run('grass:r.stream.extract', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # r.to.vect (Catchment)
        alg_params = {
            '-b': False,
            '-s': True,
            '-t': False,
            '-v': True,
            '-z': False,
            'GRASS_OUTPUT_TYPE_PARAMETER': 0,  # auto
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
            'GRASS_REGION_PARAMETER': None,
            'GRASS_VECTOR_DSCO': None,
            'GRASS_VECTOR_EXPORT_NOCAT': False,
            'GRASS_VECTOR_LCO': None,
            'column': 'value',
            'input': outputs['Rwateroutlet']['output'],
            'type': 2,  # area
            'output': parameters['CatchmentArea']
        }
        outputs['RtovectCatchment'] = processing.run('grass:r.to.vect', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['CatchmentArea'] = outputs['RtovectCatchment']['output']

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # r.to.vect (Stream)
        alg_params = {
            '-b': False,
            '-s': True,
            '-t': False,
            '-v': True,
            '-z': False,
            'GRASS_OUTPUT_TYPE_PARAMETER': 0,  # auto
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
            'GRASS_REGION_PARAMETER': None,
            'GRASS_VECTOR_DSCO': None,
            'GRASS_VECTOR_EXPORT_NOCAT': False,
            'GRASS_VECTOR_LCO': None,
            'column': 'value',
            'input': outputs['Rstreamextract']['stream_raster'],
            'type': 0,  # line
            'output': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RtovectStream'] = processing.run('grass:r.to.vect', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # Fix geometries
        alg_params = {
            'INPUT': outputs['RtovectStream']['output'],
            'METHOD': 1,  # Structure
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FixGeometries'] = processing.run('native:fixgeometries', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # Clip
        alg_params = {
            'INPUT': outputs['FixGeometries']['OUTPUT'],
            'OVERLAY': outputs['RtovectCatchment']['output'],
            'OUTPUT': parameters['StreamNetwork']
        }
        outputs['Clip'] = processing.run('native:clip', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['StreamNetwork'] = outputs['Clip']['OUTPUT']
        return results

    def name(self):
        return 'Catchment Delineation'

    def displayName(self):
        return 'Catchment Delineation'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return CatchmentDelineation()
