# Importación de módulos necesarios
import wx
import requests
import os
import sys
import api
import ui
import json
import webbrowser
import zipfile
import tempfile
from datetime import datetime
import globalPluginHandler
import globalVars

import threading
from scriptHandler import script

# Obtenemos la ruta donde se ejecuta el script
lib_dir = os.path.join(os.path.dirname(__file__), "lib")
if lib_dir not in sys.path:
	sys.path.insert(0, lib_dir)
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
def disableInSecureMode(decoratedCls):
	if globalVars.appArgs.secure:
		return globalPluginHandler.GlobalPlugin
	return decoratedCls

@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__(self):
		super().__init__()
		# URL para la carga de archivos.
		self.upload_url = "https://marco-ml.com/files/api/upload.php"
		# URL para verificar un nombre existente en el servidor.
		self.check_url = "https://marco-ml.com/files/api/check.php"
		
		
		# Ruta para el historial de archivos
		self.history_file_path = os.path.join(
			os.path.expanduser('~'), 
			'Documents', 
			'compartir_archivos', 
			'file_history.json'
		)
		# Ruta para configuraciones
		self.config_file_path = os.path.join(
			os.path.dirname(self.history_file_path), 
			'config.json'
		)
		# Asegurar que el directorio exista
		os.makedirs(os.path.dirname(self.history_file_path), exist_ok=True)


	def load_config(self):
		"""Cargar configuraciones"""
		try:
			if os.path.exists(self.config_file_path):
				with open(self.config_file_path, 'r') as f:
					return json.load(f)
			return {}
		except:
			return {}

	def save_config(self, config):
		"""Guardar configuraciones"""
		try:
			with open(self.config_file_path, 'w') as f:
				json.dump(config, f, indent=4)
		except Exception as e:
			wx.MessageBox(f"Error guardando configuración: {str(e)}", "Error", wx.ICON_ERROR)

	def check_custom_name(self, custom_name):
		"""
		Verifica si el nombre personalizado ya existe en el servidor
		"""
		try:
			response = requests.get(f"{self.check_url}?name={custom_name}")
			if response.status_code == 200:
				data = response.json()
				return data.get('exists', False)
		except:
			return False  # En caso de error, asumimos que no existe
		return False

	def save_file_history(self, file_path, share_link, expires_at):
		"""
		Guardar historial de archivos subidos en un archivo JSON
		"""
		try:
			# Cargar historial existente o inicializar lista vacía
			if os.path.exists(self.history_file_path):
				with open(self.history_file_path, 'r') as f:
					history = json.load(f)
			else:
				history = []

			# Añadir nueva entrada
			history.append({
				'file_path': file_path,
				'share_link': share_link,
				'expires_at': expires_at
			})

			# Guardar historial actualizado
			with open(self.history_file_path, 'w') as f:
				json.dump(history, f, indent=4)
		except Exception as e:
			wx.MessageBox(f"Error guardando historial: {str(e)}", "Error", wx.ICON_ERROR)

	def show_history_warning(self):
		"""Mostrar advertencia antes de mostrar historial"""
		config = self.load_config()
		
		# Si ya se ha desactivado la advertencia, ir directo al historial
		if config.get('suppress_history_warning', False):
			self.show_file_history()
			return

		# Crear diálogo de advertencia
		dialog = wx.Dialog(None, title="¡Advertencia!", size=(400, 200))
		
		main_sizer = wx.BoxSizer(wx.VERTICAL)
		
		# Mensaje de advertencia
		warning_text = wx.StaticText(dialog, label="Algunos enlaces en el historial pueden estar caducados o eliminados.\n\n¿Quieres continuar?")
		main_sizer.Add(warning_text, 0, wx.ALL | wx.ALIGN_CENTER, 20)

		# Checkbox para no mostrar de nuevo
		suppress_check = wx.CheckBox(dialog, label="&No mostrar esta advertencia de nuevo")
		main_sizer.Add(suppress_check, 0, wx.ALL | wx.ALIGN_CENTER, 10)

		# Botones
		button_sizer = wx.BoxSizer(wx.HORIZONTAL)
		ok_button = wx.Button(dialog, wx.ID_OK, "&Continuar")
		cancel_button = wx.Button(dialog, wx.ID_CANCEL, "&Volver")
		
		button_sizer.Add(ok_button, 0, wx.ALL, 5)
		button_sizer.Add(cancel_button, 0, wx.ALL, 5)
		
		main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

		dialog.SetSizer(main_sizer)
		dialog.Fit()

		if dialog.ShowModal() == wx.ID_OK:
			# Guardar preferencia de supresión si está marcada
			if suppress_check.GetValue():
				config['suppress_history_warning'] = True
				self.save_config(config)
			
			# Mostrar historial
			self.show_file_history()

		dialog.Destroy()

	def show_file_history(self):
		"""Mostrar historial de archivos"""
		try:
			# Cargar historial
			if not os.path.exists(self.history_file_path):
				wx.MessageBox("No hay historial de archivos.", "Información", wx.ICON_INFORMATION)
				return

			with open(self.history_file_path, 'r') as f:
				history = json.load(f)

			# Crear y configurar el diálogo
			dialog = wx.Dialog(wx.GetApp().GetTopWindow(), title="Historial de archivos compartidos", size=(600, 400))
		
			main_sizer = wx.BoxSizer(wx.VERTICAL)
		
			# Control de lista para el historial
			list_ctrl = wx.ListCtrl(dialog, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
			list_ctrl.InsertColumn(0, "Archivo", width=200)
			list_ctrl.InsertColumn(1, "Enlace", width=200)
			list_ctrl.InsertColumn(2, "Expira", width=100)

			# Rellenar lista con todos los elementos
			for entry in history:
				list_ctrl.Append([
					os.path.basename(entry['file_path']),
					entry['share_link'],
					entry.get('expires_at', 'Desconocido')
				])

			main_sizer.Add(list_ctrl, 1, wx.EXPAND | wx.ALL, 10)

			# Sizer horizontal de botones
			button_sizer = wx.BoxSizer(wx.HORIZONTAL)

			# Botón Abrir Enlace
			open_btn = wx.Button(dialog, label="&Abrir enlace")
			open_btn.Bind(wx.EVT_BUTTON, lambda event: self.open_selected_link(list_ctrl))
			button_sizer.Add(open_btn, 0, wx.ALL, 5)

			# Botón Copiar Enlace
			copy_btn = wx.Button(dialog, label="&Copiar enlace")
			copy_btn.Bind(wx.EVT_BUTTON, lambda event: self.copy_selected_link(list_ctrl))
			button_sizer.Add(copy_btn, 0, wx.ALL, 5)

			# Botón Eliminar
			delete_btn = wx.Button(dialog, label="&Eliminar")
			delete_btn.Bind(wx.EVT_BUTTON, 
				lambda event: self.delete_selected_entry(list_ctrl, dialog))
			button_sizer.Add(delete_btn, 0, wx.ALL, 5)

			# Botón Actualizar
			refresh_btn = wx.Button(dialog, label="&Refrescar")
			refresh_btn.Bind(wx.EVT_BUTTON, 
				lambda event: self.refresh_history(list_ctrl))
			button_sizer.Add(refresh_btn, 0, wx.ALL, 5)

			main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

			dialog.SetSizer(main_sizer)
			dialog.Layout()

			# Asociar teclas
			dialog.Bind(wx.EVT_CHAR_HOOK, 
				lambda event: self.on_dialog_key(event, dialog, list_ctrl))

			dialog.ShowModal()
			dialog.Destroy()

		except Exception as e:
			wx.MessageBox(f"Error mostrando historial: {str(e)}", "Error", wx.ICON_ERROR)

	def on_dialog_key(self, event, dialog, list_ctrl):
		"""
		Manejar eventos de teclas del diálogo
		"""
		key_code = event.GetKeyCode()
		if key_code == wx.WXK_ESCAPE:
			dialog.EndModal(wx.ID_CANCEL)
		elif key_code == wx.WXK_F5:
			self.refresh_history(list_ctrl)
		else:
			event.Skip()

	def open_selected_link(self, list_ctrl):
		"""
		Abrir enlace seleccionado en navegador predeterminado
		"""
		selected_item = list_ctrl.GetFirstSelected()
		if selected_item != -1:
			link = list_ctrl.GetItemText(selected_item, 1)
			webbrowser.open(link)

	def copy_selected_link(self, list_ctrl):
		"""
		Copiar enlace seleccionado al portapapeles
		"""
		selected_item = list_ctrl.GetFirstSelected()
		if selected_item != -1:
			link = list_ctrl.GetItemText(selected_item, 1)
			api.copyToClip(link)
			wx.MessageBox("Enlace copiado al portapapeles", "Información", wx.ICON_INFORMATION)

	def delete_selected_entry(self, list_ctrl, dialog):
		"""
		Eliminar entrada seleccionada del historial
		"""
		selected_item = list_ctrl.GetFirstSelected()
		if selected_item == -1:
			wx.MessageBox("Por favor, seleccione un archivo para eliminar", "Información", wx.ICON_INFORMATION)
			return

		try:
			# Obtener información del archivo seleccionado
			file_path = list_ctrl.GetItem(selected_item, 0).GetText()

			# Cargar historial actual
			with open(self.history_file_path, 'r') as f:
				history = json.load(f)

			# Filtrar la entrada seleccionada
			history = [entry for entry in history if os.path.basename(entry['file_path']) != file_path]

			# Guardar historial actualizado
			with open(self.history_file_path, 'w') as f:
				json.dump(history, f, indent=4)

			# Actualizar la vista
			self.refresh_history(list_ctrl)

			wx.MessageBox("Archivo eliminado del historial", "Información", wx.ICON_INFORMATION)
		except Exception as e:
			wx.MessageBox(f"Error eliminando archivo: {str(e)}", "Error", wx.ICON_ERROR)

	def refresh_history(self, list_ctrl):
		"""
		Actualizar el contenido del historial
		"""
		try:
			# Limpiar lista actual
			list_ctrl.DeleteAllItems()
		
			# Recargar historial
			with open(self.history_file_path, 'r') as f:
				history = json.load(f)

			# Rellenar lista con datos actualizados
			for entry in history:
				list_ctrl.Append([
					os.path.basename(entry['file_path']),
					entry['share_link'],
					entry.get('expires_at', 'Desconocido')
				])
			ui.message("Historial actualizado.")
		except Exception as e:
			wx.MessageBox(f"Error actualizando historial: {str(e)}", "Error", wx.ICON_ERROR)

	@script(
		description="Subir archivo al servidor y copiar enlace al portapapeles",
		category="compartir_archivos",
		gesture=None
	)
	def script_upload_file(self, gesture):
		wx.CallLater(100, self.open_file_dialog)

	@script(
		description="Mostrar historial de archivos compartidos",
		category="compartir_archivos",
		gesture=None
	)
	def script_show_file_history(self, gesture):
		wx.CallLater(100, self.show_history_warning)
	def create_zip_file(self, file_paths):
		"""
		Crea un archivo ZIP con los archivos seleccionados
		"""
		# Diálogo para elegir nombre del ZIP
		with wx.FileDialog(
			None,
			"Guardar archivo ZIP como",
			defaultDir=os.path.expanduser("~\\Documents"),
			defaultFile="archivos.zip",
			wildcard="Archivos ZIP (*.zip)|*.zip",
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
		) as saveDialog:
		
			if saveDialog.ShowModal() == wx.ID_CANCEL:
				return None
		
			zip_path = saveDialog.GetPath()
		
			try:
				# Mostrar diálogo de progreso
				progress_dialog = wx.ProgressDialog(
					"Comprimiendo archivos",
					"Preparando compresión...",
					maximum=len(file_paths),
					parent=None,
					style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
				)
			
				with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zipf:
					for idx, file_path in enumerate(file_paths, 1):
						progress_dialog.Update(
							idx, 
							f"Comprimiendo: {os.path.basename(file_path)}"
						)
						zipf.write(file_path, os.path.basename(file_path))
			
				progress_dialog.Destroy()
				return zip_path
			
			except Exception as e:
				wx.MessageBox(f"Error creando archivo ZIP: {str(e)}", "Error", wx.ICON_ERROR)
				return None
	def open_file_dialog(self):
		with wx.FileDialog(
			None, 
			"Seleccionar archivos", 
			wildcard="Todos los archivos (*.*)|*.*",
			style=wx.FD_OPEN | wx.FD_MULTIPLE  # Permitir selección múltiple
		) as fileDialog:
			if fileDialog.ShowModal() == wx.ID_CANCEL:
				ui.message("Operación cancelada")
				return

			file_paths = fileDialog.GetPaths()
		
			# Si solo se seleccionó un archivo
			if len(file_paths) == 1:
				file_path = file_paths[0]
				file_size = os.path.getsize(file_path)
				if file_size > 1024 * 1024 * 1024:
					ui.message("El archivo es demasiado grande. El límite es 1024MB.")
					return
				self.show_options_dialog(file_path)
			
			# Si se seleccionaron múltiples archivos
			else:
				total_size = sum(os.path.getsize(f) for f in file_paths)
				if total_size > 1024 * 1024 * 1024:
					ui.message("El tamaño total de los archivos excede el límite de 1024MB.")
					return
			
				# Preguntar si desea comprimir
				if wx.MessageBox(
					"Has seleccionado múltiples archivos. ¿Deseas comprimir los archivos en un ZIP?",
					"Comprimir archivos",
					wx.YES_NO | wx.ICON_QUESTION
				) == wx.YES:
					zip_path = self.create_zip_file(file_paths)
					if zip_path:
						self.show_options_dialog(zip_path, is_temp=True)
				else:
					ui.message("Solo se puede subir un archivo a la vez. Por favor, selecciona un único archivo o usa la opción de comprimir.")

	def show_options_dialog(self, file_path, is_temp=False):
		"""
		Muestra un diálogo para configurar las opciones de subida
		"""
		dialog = wx.Dialog(None, title="Opciones de subida", size=(400, 200))
		
		main_sizer = wx.BoxSizer(wx.VERTICAL)
		
		# Panel para el nombre personalizado
		name_sizer = wx.BoxSizer(wx.HORIZONTAL)
		name_label = wx.StaticText(dialog, label="Nombre personalizado (opcional):")
		name_sizer.Add(name_label, 0, wx.ALL, 5)
		name_ctrl = wx.TextCtrl(dialog)
		name_sizer.Add(name_ctrl, 1, wx.EXPAND|wx.ALL, 5)
		main_sizer.Add(name_sizer, 0, wx.EXPAND|wx.ALL, 5)

		# Panel para la expiración
		expire_sizer = wx.BoxSizer(wx.HORIZONTAL)
		expire_label = wx.StaticText(dialog, label="Tiempo de expiración (horas):")
		expire_sizer.Add(expire_label, 0, wx.ALL, 5)
		expire_ctrl = wx.SpinCtrl(dialog, min=1, max=168, initial=24)
		expire_sizer.Add(expire_ctrl, 0, wx.ALL, 5)
		main_sizer.Add(expire_sizer, 0, wx.EXPAND|wx.ALL, 5)

		info_text = wx.StaticText(dialog, label="Si no especifica un tiempo de expiración, se usarán 24 horas por defecto.")
		main_sizer.Add(info_text, 0, wx.ALL, 5)
		# Checkbox para los términos y condiciones
		terms_sizer = wx.BoxSizer(wx.HORIZONTAL)
		terms_checkbox = wx.CheckBox(dialog, label="Declaro haber leído y aceptado los términos y condiciones.")
		terms_sizer.Add(terms_checkbox, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)

		# Enlace a los términos y condiciones
		terms_link = wx.adv.HyperlinkCtrl(
			dialog, 
			id=wx.ID_ANY,
			label="Vicitar términos y condiciones",
			url=""  # URL vacía, manejaremos el clic manualmente
		)
		terms_link.Bind(wx.adv.EVT_HYPERLINK, lambda evt: webbrowser.open("https://marco-ml.com/files/api/terms.html"))
		terms_sizer.Add(terms_link, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)

		main_sizer.Add(terms_sizer, 0, wx.EXPAND|wx.ALL, 5)
		
		button_sizer = wx.BoxSizer(wx.HORIZONTAL)
		ok_button = wx.Button(dialog, wx.ID_OK, "&Subir")
		ok_button.Disable()
		cancel_button = wx.Button(dialog, wx.ID_CANCEL, "Cancelar")
		button_sizer.Add(ok_button, 0, wx.ALL, 5)
		button_sizer.Add(cancel_button, 0, wx.ALL, 5)
		main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER|wx.ALL, 5)

		def on_checkbox_change(event):
			ok_button.Enable(terms_checkbox.GetValue())

		terms_checkbox.Bind(wx.EVT_CHECKBOX, on_checkbox_change)
		dialog.SetSizer(main_sizer)
		dialog.Fit()
		
		while True:
			if dialog.ShowModal() == wx.ID_OK:
				if not terms_checkbox.GetValue():
					wx.MessageBox(
						"Debes aceptar los términos y condiciones para continuar.",
						"Términos y condiciones",
						wx.ICON_EXCLAMATION
					)
					continue
				custom_name = name_ctrl.GetValue().strip()
				expire_hours = expire_ctrl.GetValue()
				
				# Si se proporcionó un nombre personalizado, verificar duplicados
				if custom_name:
					if self.check_custom_name(custom_name):
						ui.message(f"El nombre '{custom_name}' ya está en uso. Por favor, elige otro nombre.")
						continue  # Volver a mostrar el diálogo
				
				# Si llegamos aquí, el nombre es válido o no se proporcionó ninguno
				wx.CallAfter(self.show_progress_dialog, file_path, custom_name, expire_hours)
				break
			else:
				ui.message("Operación cancelada")
				break
		
		dialog.Destroy()

	def show_progress_dialog(self, file_path, custom_name, expire_hours):
		dialog = wx.Dialog(None, title="Subiendo archivo...", size=(300, 100))
		gauge = wx.Gauge(dialog, range=100, size=(250, 25), pos=(20, 20))
		
		dialog.Show()
		
		threading.Thread(target=self.upload_file, args=(file_path, gauge, dialog, custom_name, expire_hours)).start()

	def upload_file(self, file_path, gauge, dialog, custom_name, expire_hours):
		try:
			with open(file_path, 'rb') as f:
				total_size = os.path.getsize(file_path)
				
				def callback(monitor):
					progress = int(monitor.bytes_read * 100 / total_size)
					wx.CallAfter(gauge.SetValue, progress)
				
				fields = {
					'file': (os.path.basename(file_path), f, 'application/octet-stream'),
				}
				
				if custom_name:
					fields['custom_path'] = custom_name
				if expire_hours != 24:
					fields['expire_hours'] = str(expire_hours)
				#fields['expire_hours'] = expire_hours
				
				encoder = MultipartEncoder(fields=fields)
				monitor = MultipartEncoderMonitor(encoder, callback)
				
				headers = {'Content-Type': monitor.content_type}
				response = requests.post(
					self.upload_url,
					data=monitor,
					headers=headers,
					verify=True
				)

				if response.status_code == 200:
					response_data = json.loads(response.text)
					
					if response_data.get('success'):
						share_link = response_data['download_link']
						expires_at = response_data.get('expires_at', 'desconocido')
						
						# Guardar en historial
						self.save_file_history(file_path, share_link, expires_at)
						
						api.copyToClip(share_link)
						
						expiry_message = f"Enlace copiado al portapapeles.\nExpira en: {expires_at}"
						wx.CallAfter(wx.MessageBox, 
							expiry_message,
							"Información", 
							wx.ICON_INFORMATION
						)
					else:
						wx.CallAfter(ui.message, "Error al procesar la respuesta del servidor")
				else:
					wx.CallAfter(ui.message, f"Error al subir el archivo. Código: {response.status_code}")

		except requests.exceptions.RequestException as e:
			wx.CallAfter(ui.message, f"Error en la conexión: {str(e)}")
		except json.JSONDecodeError as e:
			wx.CallAfter(ui.message, f"Error al procesar la respuesta JSON: {str(e)}")
		except Exception as e:
			wx.CallAfter(ui.message, f"Ocurrió un error: {str(e)}")
		finally:
			wx.CallAfter(dialog.Destroy)
			# Verificar si el archivo es un ZIP y eliminarlo después de la subida
			if file_path.lower().endswith('.zip'):
				try:
					wx.CallLater(2000, lambda: os.remove(file_path) if os.path.exists(file_path) else None)
				except:
					pass

	if lib_dir in sys.path:
		sys.path.remove(lib_dir)