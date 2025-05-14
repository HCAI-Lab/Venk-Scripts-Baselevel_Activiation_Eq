from flask import Flask, render_template, Response, request, send_from_directory
import queue
import threading

app = Flask(__name__)

# Queue to store log messages
log_queue = queue.Queue()

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/logs')
def stream_logs():
    def generate():
        while True:
            message = log_queue.get()  # Blocks until a new log message is available
            yield f"data: {message}\n\n"
    
    return Response(generate(), content_type="text/event-stream")



# @app.route('/update', methods=['POST'])
# def update():
#     log_entry = request.form['log']
#     log_queue.put(log_entry)  # Add log entry to the queue
#     return "", 204  # No content response


@app.route('/update', methods=['POST'])
def update():
    log_entry = request.form['log']
    
    if log_entry == "CLEAR_LOGS":
        with log_queue.mutex:
            log_queue.queue.clear()  # Clear all previous logs

    log_queue.put(log_entry)  # Add log entry to the queue
    return "", 204



if __name__ == '__main__':
    app.run(debug=True, port=5001, threaded=True)
