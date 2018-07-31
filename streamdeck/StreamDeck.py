import hid
import threading
import cv2

class DeviceManager:
    """ The vendor Id of Elgato  """
    VID_ELGATO = 4057
    """ The product Id of the StreamDeck """
    PID_STREAMDECK = 96

    def enumerate(self):
        """
        Enumerate all detected StreamDeck devices.

        Return: list of `StreamDeck` instances, one for each detected device.
        """
        decks = hid.enumerate(vendor_id=self.VID_ELGATO, product_id=self.PID_STREAMDECK)
        return [StreamDeck(d) for d in decks]

class StreamDeck:
    KEY_COUNT = 15
    KEY_COLS = 5
    KEY_ROWS = 3

    KEY_WIDTH = 72
    KEY_HEIGHT = 72
    KEY_PIXEL_DEPTH = 3
    KEY_PIXEL_ORDER = "BGR"

    KEY_IMG_SIZE = KEY_WIDTH * KEY_HEIGHT * KEY_PIXEL_DEPTH
    KEY_IMG_DIM = (KEY_WIDTH, KEY_HEIGHT)

    IMG_OUT_REPORT_PAGE1_HEADER = bytearray([
        0x02, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x42, 0x4d, 0xf6, 0x3c, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x36, 0x00, 0x00, 0x00, 0x28, 0x00,
        0x00, 0x00, 0x48, 0x00, 0x00, 0x00, 0x48, 0x00,
        0x00, 0x00, 0x01, 0x00, 0x18, 0x00, 0x00, 0x00,
        0x00, 0x00, 0xc0, 0x3c, 0x00, 0x00, 0xc4, 0x0e,
        0x00, 0x00, 0xc4, 0x0e, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    ])
    IMG_OUT_REPORT_PAGE2_HEADER = bytearray([
        0x02, 0x01, 0x02, 0x00, 0x01, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    ])

    def __init__(self, device_info):
        self.device_info = device_info
        self.hid_device = hid.device()
        self.last_key_states = [False] * self.KEY_COUNT

        self.key_callbacks = [set() for i in range(self.KEY_COUNT)]

        self.listen_thread = None
        self.listen_thread_running = False

    def __del__(self):
        self.close()

    @staticmethod
    def is_valid_key(key):
        return int(key) >= 0 and int(key)  < StreamDeck.KEY_COUNT

    def add_key_callback(self, key, callback):
        if not self.is_valid_key(key): raise IndexError("Invalid key index {}.".format(key))
        self.key_callbacks[int(key)].add(callback)

    def remove_key_callback(self, key, callback):
        if not self.is_valid_key(key): raise IndexError("Invalid key index {}.".format(key))
        self.key_callbacks[int(key)].discard(callback)

    def open(self):
        """
        Opens the device for input/output. This must be called prior to setting
        or retrieving any device state.
        """
        # Open device
        self.hid_device.open_path(self.device_info['path'])
        
        # Start read thread
        self.listen_thread_running = True
        self.listen_thread = threading.Thread(target=self._listen_to_device, daemon=True)
        self.listen_thread.start()

    def close(self):
        """ Closes the device for input/output."""
        # Close device
        self.hid_device.close()
        # Stop read thread
        self.listen_thread_running = False
        self.listen_thread.join()

    def set_brightness(self, percent):
        if type(percent) is float:
            percent = int(100.0 * percent)

        percent = min(max(percent, 0), 100)

        payload = bytearray(17)
        payload[0:6] = [0x05, 0x55, 0xaa, 0xd1, 0x01, percent]
        self.hid_device.send_feature_report(payload)

    def set_key_img_from_src(self, key, src):
        """ 
        Sets the image of a button on the StremDeck to the image at the give path. 
        
        Parameters
        -----------
        key : int
            The index of the key whose image will be set
        src : str 
            The path to the image source
        """
        
        img = cv2.imread(src, cv2.IMREAD_COLOR) # Image has to be in BGR format. Fortunaltelly cv2 reads color images as BGR
        img = cv2.resize(img, self.KEY_IMG_DIM, interpolation=cv2.INTER_AREA) # Resize image to correct size
        img = cv2.flip(img, 1) # Flip image vertically
        self.set_key_img(key, img.flat)

    def set_key_img(self, key, img_buffer):
        """
        Sets the image of a button on the StremDeck to the given image. The
        image being set should be in the correct format for the device, as an
        enumerable collection of pixels. If the param 'img_bytes' is 'None' the key
        will be set to an all black image. 

        Parameters: 
        -----------
        key : int
            The index of the key whose image will be set
        img_buffer : enumerable collection
            A 1-D enumerable collection containing the raw, 
            uncompressed pixel data of the image, encoded in BGR.
        """
        # Convert 'img_buffer' to byte array.
        # If 'img_buffer' is None, set 'img_bytes' to an array of size 'StreamDeck.KEY_IMG_SIZE',
        # filled with zero bytes. This results in a black key image.
        img_bytes = bytes(img_buffer or StreamDeck.KEY_IMG_SIZE)

        if not self.is_valid_key(key): raise IndexError("Invalid key index {}.".format(key))
            
        # Has to be exactly 72x72 BGR pixels = 72x72x3 integers
        if len(img_bytes) != self.KEY_IMG_SIZE: raise ValueError("Invalid image size {}.".format(len(img_bytes)))

        IMAGE_BYTES_PAGE_1 = 2583 * 3

        page_headers = self._get_img_out_report_page_headers_for_key(key)
        page_1 = bytes(page_headers[0]) + img_bytes[ : IMAGE_BYTES_PAGE_1]
        page_2 = bytes(page_headers[1]) + img_bytes[IMAGE_BYTES_PAGE_1 : ]

        self.hid_device.write(page_1)
        self.hid_device.write(page_2)

    def clear_key_img(self, key):
        self.set_key_img(key, None)

    def clear(self):
        for key in range(StreamDeck.KEY_COUNT):
            self.clear_key_img(key)

    def _get_img_out_report_page_headers_for_key(self, key):
        """
        Returns the page headers for the two output reports that are sent to the Stream Deck,
        to change the image of the specifed key.

        Parameters
        ----------
        key : int
            The index of the key (0<=key<KEY_COUNT) 
        """
        if not self.is_valid_key(key): raise IndexError("Invalid key index {}.".format(key))

        key_num = key+1 # Convert key index to key number
        
        # Create the page headers. Only byte 5 changes. It indicates which key is targeted.
        page1_header = StreamDeck.IMG_OUT_REPORT_PAGE1_HEADER.copy()
        page2_header = StreamDeck.IMG_OUT_REPORT_PAGE2_HEADER.copy()
        page1_header[5] = page2_header[5] = key_num

        return (page1_header, page2_header)

    def _listen_to_device(self):
        """
        Listening for button state changes on the underlying device, caching the new states and firing off
        any registered callbacks.
        """
        while self.listen_thread_running:
            try:
                payload = self.hid_device.read(17, 1)
            except ValueError as e:
                self.listen_thread_run = False

            if len(payload):
                new_key_states = [bool(s) for s in payload[1:]]

                for key, (old_state, new_state) in enumerate(zip(self.last_key_states, new_key_states)):
                    if old_state != new_state:
                        key_callbacks = self.key_callbacks[key]
                        for key_callback in key_callbacks: key_callback(key,old_state,new_state)

                self.last_key_states = new_key_states