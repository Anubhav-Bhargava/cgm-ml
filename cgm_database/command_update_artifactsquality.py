import warnings
warnings.filterwarnings("ignore")
import sys
sys.path.insert(0, "..")
import os
import dbutils
import math
import numpy as np
from cgmcore import modelutils, utils
import logging
logging.getLogger("tensorflow").setLevel(logging.ERROR)
import progressbar
import psycopg2
import glob
import pickle
import cv2
import posenet
import tensorflow as tf
import time



def main():
    
    commands = ["bluriness", "pointcloud","posenet"]
    
    if len(sys.argv) == 1 or sys.argv[1] not in commands:
        print("ERROR! Must use one of", commands)
    if sys.argv[1] == "bluriness":
        update_artifactsquality_with_bluriness()
    elif sys.argv[1] == "pointcloud":
        update_artifactsquality_with_pointcloud_data()
    elif sys.argv[1] == "posenet":
        update_artifactsquality_with_posenet()
    else:
        print("ERROR!")
   
   
  
  
    
def update_artifactsquality_with_bluriness():
    # Get all images.
    sql_script = "SELECT id, path FROM artifact WHERE type='jpg'"
    db_connector = dbutils.connect_to_main_database()
    image_entries = db_connector.execute(sql_script, fetch_all=True)
    print("Found {} images.".format(len(image_entries)))
    
    db_type = "rgb"
    db_key = "bluriness"
    
    def process_image_entries(image_entries):
        db_connector = dbutils.connect_to_main_database()
        
        # Go through all entries.
        bar = progressbar.ProgressBar(max_value=len(image_entries))
        for index, (artifact_id, path) in enumerate(image_entries):
            bar.update(index)
            
            # Check if there is already an entry.
            select_sql_statement = ""
            select_sql_statement += "SELECT COUNT(*) FROM artifact_quality"
            select_sql_statement += " WHERE artifact_id='{}'".format(artifact_id)
            select_sql_statement += " AND type='{}'".format(db_type)
            select_sql_statement += " AND key='{}'".format(db_key)
            results = db_connector.execute(select_sql_statement, fetch_one=True)[0]
            
            # There is an entry. Skip
            if results != 0:
                continue
            bluriness = get_blur_variance(path)
            
            # Create an SQL statement for insertion.
            sql_statement = ""
            sql_statement += "INSERT INTO artifact_quality (type, key, value, artifact_id, misc)"
            sql_statement += " VALUES(\'{}\', \'{}\', \'{}\', \'{}\', \'{}\');".format(db_type, db_key, bluriness, artifact_id, "")
            # Call database.
            result = db_connector.execute(sql_statement)
            
        bar.finish()
    
    # Run this in multiprocess mode.
    utils.multiprocess(
        image_entries, 
        process_method=process_image_entries, 
        process_individial_entries=False, 
        progressbar=False
    )
    print("Done.")
    
    
def get_blur_variance(image_path):
    try:
        image = cv2.imread(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur_variance = cv2.Laplacian(image, cv2.CV_64F).var()
        return blur_variance
    except Exception as e:
        print("\n", image_path, e)
        error = True
        error_message = str(e)
    except ValueError as e:
        print("\n", image_path, e)
        error = True
        error_message = str(e)
    return None


def update_artifactsquality_with_pointcloud_data():
    # Get all pointclouds.
    sql_script = "SELECT id, path FROM artifact WHERE type='pcd'"
    db_connector = dbutils.connect_to_main_database()
    pointcloud_entries = db_connector.execute(sql_script, fetch_all=True)
    print("Found {} pointclouds.".format(len(pointcloud_entries)))
    
    db_type = "pcd"
    
    def process_pointcloud_entries(pointcloud_entries):
        db_connector = dbutils.connect_to_main_database()
        
        # Go through all entries.
        bar = progressbar.ProgressBar(max_value=len(pointcloud_entries))
        for index, (artifact_id, path) in enumerate(pointcloud_entries):
            bar.update(index)
            
            pointcloud_values = get_pointcloud_values(path)
            for db_key, db_value in pointcloud_values.items():
            
                # Check if there is already an entry.
                select_sql_statement = ""
                select_sql_statement += "SELECT COUNT(*) FROM artifact_quality"
                select_sql_statement += " WHERE artifact_id='{}'".format(artifact_id)
                select_sql_statement += " AND type='{}'".format(db_type)
                select_sql_statement += " AND key='{}'".format(db_key)
                results = db_connector.execute(select_sql_statement, fetch_one=True)[0]
                
                # There is an entry. Skip
                if results != 0:
                    continue

                # Create an SQL statement for insertion.
                sql_statement = ""
                sql_statement += "INSERT INTO artifact_quality (type, key, value, artifact_id, misc)"
                sql_statement += " VALUES(\'{}\', \'{}\', \'{}\', \'{}\', \'{}\');".format(db_type, db_key, db_value, artifact_id, "")
                
                # Call database.
                try:
                    result = db_connector.execute(sql_statement)
                except:
                    print(sql_statement, pointcloud_values)
                    exit(0)
            
        bar.finish()
    
    # Run this in multiprocess mode.
    utils.multiprocess(
        pointcloud_entries, 
        process_method=process_pointcloud_entries, 
        process_individial_entries=False, 
        progressbar=False
    )
    print("Done.")

    
def get_pointcloud_values(path):
    number_of_points = 0
    confidence_min = 0.0
    confidence_avg = 0.0
    confidence_std = 0.0
    confidence_max = 0.0
    
    centroid_x = 0.0
    centroid_y = 0.0
    centroid_z = 0.0
    
    stdev_x = 0.0
    stdev_y = 0.0
    stdev_z = 0.0
    
    error = False
    error_message = ""
    
    try:
        pointcloud = utils.load_pcd_as_ndarray(path)
        number_of_points = len(pointcloud)
        confidence_min = float(np.min(pointcloud[:,3]))
        confidence_avg = float(np.mean(pointcloud[:,3]))
        confidence_std = float(np.std(pointcloud[:,3]))
        confidence_max = float(np.max(pointcloud[:,3]))
        
        centroid_x = float(np.mean(pointcloud[:,0]))
        centroid_y = float(np.mean(pointcloud[:,1]))
        centroid_z = float(np.mean(pointcloud[:,2]))
        
        stdev_x = float(np.mean(pointcloud[:,0]))
        stdev_y = float(np.mean(pointcloud[:,1]))
        stdev_z = float(np.mean(pointcloud[:,2]))
        
    except Exception as e:
        print("\n", path, e)
        error = True
        error_message = str(e)
    except ValueError as e:
        print("\n", path, e)
        error = True
        error_message = str(e)
    
    values = {}
    values["number_of_points"] = number_of_points
    values["confidence_min"] = confidence_min
    values["confidence_avg"] = confidence_avg
    values["confidence_std"] = confidence_std
    values["confidence_max"] = confidence_max
    values["centroid_x"] = centroid_x
    values["centroid_y"] = centroid_y
    values["centroid_z"] = centroid_z
    values["stdev_x"] = stdev_x
    values["stdev_y"] = stdev_y
    values["stdev_z"] = stdev_z
    return values
    
# TODO make this work again    
def update_artifactsquality_with_model():

    # Check the arguments.
    if len(sys.argv) != 2:
        raise Exception("ERROR! Must provide model filename.")
    model_path = sys.argv[1]
    if not os.path.exists(model_path):
        raise Exception("ERROR! \"{}\" does not exist.".format(model_path))
    if not os.path.isfile(model_path):
        raise Exception("ERROR! \"{}\" is not a file.".format(model_path))

    # Get the training QR-codes.
    search_path = os.path.join(os.path.dirname(model_path), "*.p")
    paths = glob.glob(search_path)
    details_path = [path for path in paths if "details" in path][0]
    details = pickle.load(open(details_path, "rb"))
    qrcodes_train = details["qrcodes_train"]
        
    # Create database connection.
    db_connector = dbutils.connect_to_main_database()

    # Query the database for artifacts.
    print("Getting all artifacts...")
    sql_statement = ""
    # Select all artifacts.
    sql_statement += "SELECT pointcloud_data.id, pointcloud_data.path, measurements.height_cms, pointcloud_data.qrcode FROM pointcloud_data"
    # Join them with measurements.
    sql_statement += " INNER JOIN measurements ON pointcloud_data.measurement_id=measurements.id"
    # Only take into account manual measurements.
    sql_statement += " WHERE measurements.type=\'manual\'"
    artifacts = db_connector.execute(sql_statement, fetch_all=True)
    print("Found {} artifacts.".format(len(artifacts)))

    # Method for processing a set of artifacts.
    # Note: This method will run in its own process.
    def process_artifacts(artifacts):
        
         # Create database connection.
        db_connector = dbutils.connect_to_main_database()
    
        # Load the model first.
        model = load_model(model_path)
        model_name = model_path.split("/")[-2]
        
        # Evaluate and create SQL-statements.
        bar = progressbar.ProgressBar(max_value=len(artifacts))
        for artifact_index, artifact in enumerate(artifacts):
            bar.update(artifact_index)

            # Execute SQL statement.
            try:
                # Load the artifact and evaluate.
                artifact_id, pcd_path, target_height, qrcode = artifact
                pcd_array = utils.load_pcd_as_ndarray(pcd_path)
                pcd_array = utils.subsample_pointcloud(pcd_array, 10000)
                mse, mae = model.evaluate(np.expand_dims(pcd_array, axis=0), np.array([target_height]), verbose=0)
                if qrcode in qrcodes_train:
                    misc = "training"
                else:
                    misc = "nottraining"
                
                # Create an SQL statement.
                sql_statement = ""
                sql_statement += "INSERT INTO artifact_quality (type, key, value, artifact_id, misc)"
                sql_statement += " VALUES(\'{}\', \'{}\', \'{}\', \'{}\', \'{}\');".format(model_name, "mae", mae, artifact_id, misc)

                # Call database.
                result = db_connector.execute(sql_statement)
            except psycopg2.IntegrityError:
                print("Already in DB. Skipped.", pcd_path)
            except ValueError:
                print("Skipped.", pcd_path)
        bar.finish()

    # Run this in multiprocess mode.
    utils.multiprocess(artifacts, process_method=process_artifacts, process_individial_entries=False, progressbar=False)
    print("Done.")
        
        
def load_model(model_path):

    input_shape = (10000, 3)
    output_size = 1
    model = modelutils.create_point_net(input_shape, output_size, hidden_sizes = [512, 256, 128])
    model.load_weights(model_path)
    model.compile(
        optimizer="rmsprop",
        loss="mse",
        metrics=["mae"]
    )
    return model 

def update_artifactsquality_with_posenet():
    # Get all images.
    sql_script = "SELECT id, path FROM artifact WHERE type='jpg'"
    db_connector = dbutils.connect_to_main_database()
    image_entries = db_connector.execute(sql_script, fetch_all=True)
    print("Found {} images.".format(len(image_entries)))
    
    db_type = "rgb"
    db_key = "No of People"
    
    def process_image_entries(image_entries):
        db_connector = dbutils.connect_to_main_database()
        
        # Go through all entries.
        bar = progressbar.ProgressBar(max_value=len(image_entries))
        for index, (artifact_id, path) in enumerate(image_entries):
            bar.update(index)
            
            # Check if there is already an entry.
            select_sql_statement = ""
            select_sql_statement += "SELECT COUNT(*) FROM artifact_quality"
            select_sql_statement += " WHERE artifact_id='{}'".format(artifact_id)
            select_sql_statement += " AND type='{}'".format(db_type)
            select_sql_statement += " AND key='{}'".format(db_key)
            results = db_connector.execute(select_sql_statement, fetch_one=True)[0]
            
            # There is an entry. Skip
            if results != 0:
                continue
            Pose = get_pose(path)
            
            # Create an SQL statement for insertion.
            sql_statement = ""
            sql_statement += "INSERT INTO artifact_quality (type, key, value, artifact_id, misc)"
            sql_statement += " VALUES(\'{}\', \'{}\', \'{}\', \'{}\', \'{}\');".format(db_type, db_key, Pose, artifact_id, "")
            # Call database.
            result = db_connector.execute(sql_statement)
            
        bar.finish()
    
    # Run this in multiprocess mode.
    utils.multiprocess(
        image_entries, 
        process_method=process_image_entries, 
        process_individial_entries=False, 
        progressbar=False,
        number_of_workers=1
    )
    print("Done.")

    
def get_pose(image_path):
    #try:
    with tf.Session() as sess:
        model_cfg, model_outputs = posenet.load_model(101, sess)
        output_stride = model_cfg['output_stride']

        start = time.time()
        input_image, draw_image, output_scale = posenet.read_imgfile(
            image_path, scale_factor=1, output_stride=output_stride)

        heatmaps_result, offsets_result, displacement_fwd_result, displacement_bwd_result = sess.run(
            model_outputs,
            feed_dict={'image:0': input_image}
        )

        pose_scores, keypoint_scores, keypoint_coords = posenet.decode_multiple_poses(
            heatmaps_result.squeeze(axis=0),
            offsets_result.squeeze(axis=0),
            displacement_fwd_result.squeeze(axis=0),
            displacement_bwd_result.squeeze(axis=0),
            output_stride=output_stride,
            max_pose_detections=10,
            min_pose_score=0.25)

        keypoint_coords *= output_scale

        
        print()
        print("Results for image: %s" % 'image_path')
        count=0;
        for pi in range(len(pose_scores)):
            if pose_scores[pi] == 0.:
                break
            count=count+1
        return count
  #  except Exception as e:
   ##     error = True
   #     error_message = str(e)
    #except ValueError as e:
    #    print("\n", image_path, e)
    #    error = True
    #    error_message = str(e)
    return None

if __name__ == "__main__":
    main()