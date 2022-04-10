empty_layer_w_empty_feature = QgsVectorLayer()
empty_input_feature = QgsFeature()
empty_input_feature.setFields(empty_layer_w_empty_feature.fields())

with edit(empty_layer_w_empty_feature):
    empty_layer_w_empty_feature.addFeature(empty_input_feature)

empty_feature = QgsFeature()