#-*- coding:utf-8 -*-
import os
import time
import json
import warnings
from utils import data_utils
import numpy as np
import tensorflow as tf
from text_rnn import TextRNN
from sklearn.externals import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

warnings.filterwarnings("ignore")

# Parameters
# ==================================================

# Data loading parameters
tf.flags.DEFINE_string('x_data_file', '../data/word_data/pad_data_to_id/pad_data_to_id_600.txt', "Data source for the text data")
tf.flags.DEFINE_string('y_data_file', '../data/doc_cat_id.txt', "Data source for the text data")
tf.flags.DEFINE_float('test_size', 0.05, "Percentage of data to use for validation and test (default: 0.05)")
tf.flags.DEFINE_integer('vocab_size', 236444, "Select words to build vocabulary, according to term frequency (default: 9000)")
tf.flags.DEFINE_integer('sequence_length', 600, "Padding sentences to same length, cut off when necessary (default: 100)")
tf.flags.DEFINE_integer('num_classes', 11, "Number of classes")
0
# Model hyperparameters
tf.flags.DEFINE_integer('embedding_size', 256, "Dimension of word embedding (default: 128)")
tf.flags.DEFINE_integer('rnn_size', 100, "Dimension of rnn layer (default: 100)")
tf.flags.DEFINE_integer('num_layers', 1, "Number of rnn layer (default: 1)")
tf.flags.DEFINE_integer('attention_size', 100, "Dimension of attention layer (default: 100)")
tf.flags.DEFINE_float('dropout_keep_prob', 0.5, "Dropout keep probability (default: 0.5)")
tf.flags.DEFINE_float('learning_rate', 0.001, "Learning rate for model training (default: 0.001)")
tf.flags.DEFINE_float('grad_clip', 5.0, "Gradients clipping threshold (default: 5.0)")

# Training parameters
tf.flags.DEFINE_integer('batch_size', 64, "Batch size (default: 128)")
tf.flags.DEFINE_integer("num_epochs", 5, "Number of training epochs (default: 10)")
tf.flags.DEFINE_string('init_embedding_path', None, "Using pre-trained word embedding, npy file format")
tf.flags.DEFINE_string('init_model_path', None, "Continue training from saved model at this path")
tf.flags.DEFINE_integer('evaluate_every', 50, "Evaluate model on val set after this many steps (default: 50)")

# Tensorflow parameters
tf.flags.DEFINE_boolean('allow_soft_placement', True, "Allow device soft device placement (default: True)")
tf.flags.DEFINE_boolean('log_device_placement', False, "Log placement of ops on devices (default: False)")
tf.flags.DEFINE_boolean('gpu_allow_growth', True, "GPU memory allocation mode (default: True)")

FLAGS = tf.flags.FLAGS
# FLAGS._parse_flags()
print("\nParameters:")
for param, value in sorted(FLAGS.__flags.items()):
    print("{} = {}".format(param.upper(), value))
print("")


def train_rnn():
    # Data Preparation
    # ==================================================

    if FLAGS.init_embedding_path is not None:
        embedding = np.load(FLAGS.init_embedding_path)
        print("Using pre-trained word embedding which shape is {}\n".format(embedding.shape))
        FLAGS.vocab_size = embedding.shape[0]
        FLAGS.embedding_size = embedding.shape[1]

    if FLAGS.init_model_path is not None:
        assert os.path.isdir(FLAGS.init_model_path), "init_model_path must be a directory\n"
        ckpt = tf.train.get_checkpoint_state(FLAGS.init_model_path)
        assert ckpt, "No checkpoint found in {}\n".format(FLAGS.init_model_path)
        assert ckpt.model_checkpoint_path, "No model_checkpoint_path found in checkpoint\n"

    # Create root directory
    timestamp = str(int(time.time()))
    root_dir = os.path.join(os.path.curdir, 'runs', 'textrnn', 'trained_result_' + timestamp)
    os.makedirs(root_dir)

    # Load data
    # print("Loading data...\n")
    # x, y = data_helpers.load_data(FLAGS.data_file, FLAGS.sequence_length, FLAGS.vocab_size, root_dir=root_dir)
    # FLAGS.num_classes = len(y[0])
    print("Loading data...\n")
    x_data = np.loadtxt(FLAGS.x_data_file)
    y_data = np.loadtxt(FLAGS.y_data_file)
    print("data load finished")

    # Split dataset
    # x_train, x_test, y_train, y_test = train_test_split(x_data, y_data, test_size=FLAGS.test_size, stratify=y_data, random_state=0)
    # x_val, x_test, y_val, y_test = train_test_split(x_test, y_test, test_size=0.5, random_state=0)

    # Training
    # ==================================================
    with tf.Graph().as_default():
        tf_config = tf.ConfigProto(
            allow_soft_placement=FLAGS.allow_soft_placement,
            log_device_placement=FLAGS.log_device_placement)
        tf_config.gpu_options.allow_growth = FLAGS.gpu_allow_growth

        with tf.Session(config=tf_config).as_default() as sess:
            rnn = TextRNN(
		vocab_size=FLAGS.vocab_size,
		embedding_size=FLAGS.embedding_size,
		sequence_length=FLAGS.sequence_length,
		rnn_size=FLAGS.rnn_size,
                num_layers=FLAGS.num_layers,
                attention_size=FLAGS.attention_size,
            	num_classes=FLAGS.num_classes,
		learning_rate=FLAGS.learning_rate,
		grad_clip=FLAGS.grad_clip)

            # Output directory for models and summaries
            out_dir = os.path.abspath(root_dir)
            print("Writing to {}...\n".format(out_dir))

            # Summaries for loss and accuracy
            tf.summary.scalar("loss", rnn.loss)
            tf.summary.scalar("accuracy", rnn.accuracy)
            merged_summary = tf.summary.merge_all()

            # Summaries dictionary
            train_summary_dir = os.path.join(out_dir, 'summaries', 'train')
            val_summary_dir = os.path.join(out_dir, 'summaries', 'val')
            train_summary_writer = tf.summary.FileWriter(train_summary_dir, sess.graph)
            val_summary_writer = tf.summary.FileWriter(val_summary_dir, sess.graph)

            # Checkpoint directory, will not create itself
            checkpoint_dir = os.path.abspath(os.path.join(out_dir, 'checkpoints'))
            checkpoint_prefix = os.path.join(checkpoint_dir, 'model.ckpt')
            if not os.path.exists(checkpoint_dir):
                os.makedirs(checkpoint_dir)
            saver = tf.train.Saver(tf.global_variables(), max_to_keep=1)

            # Initialize all variables
            sess.run(tf.global_variables_initializer())

            # Using pre-trained word embedding
            if FLAGS.init_embedding_path is not None:
                sess.run(rnn.embedding.assign(embedding))
                del embedding

            # Continue training from saved model
            if FLAGS.init_model_path is not None:
                saver.restore(sess, ckpt.model_checkpoint_path)

            # Training start
            print("Start training...\n")
            best_at_step = 0
            best_val_accuracy = 0
            train_batches = data_utils.batch_iter(list(zip(x_data, y_data)), FLAGS.batch_size)
            start = time.time()
            rnn_feature_temp = []
            for batch in train_batches:
                # Training model on x_batch and y_batch
                x_batch, y_batch = zip(*batch)
                # seq_len_train = data_helpers.real_len(x_batch)
                seq_len_train = data_utils.real_len(x_batch)
                feed_dict = {rnn.input_x: x_batch, rnn.input_y: y_batch, rnn.seq_len: seq_len_train, rnn.keep_prob: FLAGS.dropout_keep_prob}
                attention_output, _, global_step, train_summaries, train_loss, train_accuracy = sess.run([rnn.attention_output,rnn.train_op, rnn.global_step,
                        merged_summary, rnn.loss, rnn.accuracy], feed_dict=feed_dict)
                rnn_feature_temp.append(attention_output.tolist())
            print(rnn_feature_temp[0:2])
            print(len(rnn_feature_temp))
            np.savetxt("../data/word_data/word_dim/word_rnn_attention_embeddings_600_dim256.txt", np.array(rnn_feature_temp).reshape(20480,200))

if __name__ == '__main__':
    os.system("ulimit -m 15000000")
    train_rnn()
