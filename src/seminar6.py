"""Seminar 6. Image Binary Classification with Keras. ML ops."""
import argparse
import glob
import os
import zipfile
import shutil
from urllib.request import urlretrieve
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.io import read_file, write_file
from tensorflow.image import decode_image
from tensorflow.keras.models import load_model
import boto3
import dotenv

DATA_URL = 'https://storage.yandexcloud.net/fa-bucket/cats_dogs_train.zip'
PATH_TO_DATA_ZIP = '../data/raw/cats_dogs_train.zip'
PATH_TO_DATA = '../data/raw/cats_dogs_train'
PATH_TO_MODEL = '../models/model_6'
BUCKET_NAME = 'neuralnets2023'
# todo fix your git user name and copy .env to project root
YOUR_GIT_USER = 'Ekaterina-Gorodkova'

image_size = (180, 180)

batch_size = 64


def download_data():
    """Pipeline: download and extract data"""
    if not os.path.exists(PATH_TO_DATA_ZIP):
        print('Downloading data...')
        urlretrieve(DATA_URL, PATH_TO_DATA_ZIP)
    else:
        print('Data is already downloaded!')

    if not os.path.exists(PATH_TO_DATA):
        print('Extracting data...')
        with zipfile.ZipFile(PATH_TO_DATA_ZIP, 'r') as zip_ref:
            zip_ref.extractall(PATH_TO_DATA)
    else:
        print('Data is already extracted!')


def make_model(input_shape, num_classes):
    inputs = keras.Input(shape=input_shape)
    # Entry block
    x = layers.Rescaling(1.0 / 255)(inputs)
    x = layers.Conv2D(128, 3, strides=2, padding="same")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)

    previous_block_activation = x  # Set aside residual

    for size in [256, 512, 728]:
        x = layers.Activation("relu")(x)
        x = layers.SeparableConv2D(size, 3, padding="same")(x)
        x = layers.BatchNormalization()(x)

        x = layers.Activation("relu")(x)
        x = layers.SeparableConv2D(size, 3, padding="same")(x)
        x = layers.BatchNormalization()(x)

        x = layers.MaxPooling2D(3, strides=2, padding="same")(x)

        # Project residual
        residual = layers.Conv2D(size, 1, strides=2, padding="same")(
            previous_block_activation
        )
        x = layers.add([x, residual])  # Add back residual
        previous_block_activation = x  # Set aside next residual

    x = layers.SeparableConv2D(1024, 3, padding="same")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)

    x = layers.GlobalAveragePooling2D()(x)
    if num_classes == 2:
        activation = "sigmoid"
        units = 1
    else:
        activation = "softmax"
        units = num_classes

    x = layers.Dropout(0.5)(x)
    outputs = layers.Dense(units, activation=activation)(x)
    return keras.Model(inputs, outputs)


def fi():
    num_deleted = 0
    for folder_name in ("Cat", "Dog"):
        folder_path = os.path.join(PATH_TO_DATA + "/PetImages", folder_name, '/*.jpg')
        for image in sorted(glob.glob(folder_path)):
            img = read_file(str(image))
            img = decode_image(img)
            if img.shape[2] != 3:
                num_deleted += 1
                os.remove(image)
    print("Deleted %d images" % num_deleted)


def confi():
    train_ds, val_ds = tf.keras.utils.image_dataset_from_directory(
        PATH_TO_DATA+"/PetImages",
        validation_split=0.2,
        subset="both",
        seed=1337,
        image_size=image_size,
        batch_size=batch_size,
    )

    data_augmentation = keras.Sequential(
        [
            layers.RandomFlip("horizontal"),
            layers.RandomRotation(0.1),
        ]
    )

    # Apply `data_augmentation` to the training images.
    train_ds = train_ds.map(
        lambda img, label: (data_augmentation(img), label),
        num_parallel_calls=tf.data.AUTOTUNE,
    )

    # Prefetching samples in GPU memory helps maximize GPU utilization.
    train_ds = train_ds.prefetch(tf.data.AUTOTUNE)
    val_ds = val_ds.prefetch(tf.data.AUTOTUNE)

    return train_ds, val_ds


def train():
    print('Training model')
    """Pipeline: Build, train and save model to models/model_6"""
    # Todo: Copy some code from seminar5 and https://keras.io/examples/vision/image_classification_from_scratch/
    train_ds, val_ds = confi()

    ############
    model = make_model(input_shape=image_size + (3,), num_classes=2)
    epochs = 4

    callbacks = [
        keras.callbacks.ModelCheckpoint("save_at_{epoch}.keras"),
    ]
    model.compile(
        optimizer=keras.optimizers.Adam(1e-3),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    model.fit(
        train_ds,
        epochs=epochs,
        callbacks=callbacks,
        validation_data=val_ds,
    )
    model.save(PATH_TO_MODEL)


def load(fb):
    # Загрузка сохраненной модели
    loaded_model = load_model(fb)
    loaded_model.save(PATH_TO_MODEL)

def upload():
    """Pipeline: Upload model to S3 storage"""
    print('Upload model')
    zip_model_path = PATH_TO_MODEL+'.zip'
    shutil.make_archive(base_name=PATH_TO_MODEL,
                        format='zip',
                        root_dir=PATH_TO_MODEL)

    config = dotenv.dotenv_values('.env')

    ACCESS_KEY = config['ACCESS_KEY']
    SECRET_KEY = config['SECRET_KEY']

    client = boto3.client(
        's3',
        endpoint_url='https://storage.yandexcloud.net',
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY
    )

    client.upload_file(zip_model_path, BUCKET_NAME, f'{YOUR_GIT_USER}/model_6.zip')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='src/seminar6.py',
        description='Typical DL lifecycle pipelines.')
    parser.add_argument('--download', action='store_true', help='Download images and extract to data/raw directory')
    parser.add_argument('--train', action='store_true', help='Build, train and save model to models/seminar6_model')
    parser.add_argument('--saved', action='store_true', help='imp saved mod')
    parser.add_argument('--upload', action='store_true', help='Upload model to S3 storage')
    args = parser.parse_args()
    if args.download:
        download_data()
        fi()
    if args.train:
        train()
    if args.saved:
        load('save_at_3.keras')
    if args.upload:
        upload()