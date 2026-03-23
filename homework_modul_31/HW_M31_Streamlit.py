import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import vl_convert as vlc
alt.data_transformers.disable_max_rows()


# Инициализируем переменную
col_to_show_chart_x = None 
col_to_show_chart_y = None 

#Функция обработки загружаемого файла
@st.cache_data()
def safe_load_table(file, verbose=False):
        df = None
        try:
            if file.name.endswith(".csv"):
                encodings = ["utf-8", "cp1251"]
                for enc in encodings:
                    try:
                        df = pd.read_csv(file, encoding=enc,sep=None, engine='python')
                        break
                    except UnicodeDecodeError:
                        file.seek(0)
            elif file.name.endswith(".xls") or file.name.endswith(".xlsx"):
                df = pd.read_excel(file)
        except pd.errors.EmptyDataError:
            if verbose:
                st.error("Ошибка: Файл пустой")
        except Exception as e:
            if verbose:
                st.error(f"Неожиданная ошибка: {str(e)}")
        return df

# Функция очищает список выбранных колонок после загрузки файла
def reset_selection_columns():
    st.session_state.cols = []
    st.session_state.sidebar_radio = "Загрузка csv и просмотр данных"
    reset_char_selectboxes()
    
# Функция очищает список выбранных колонок после смены графика
def reset_char_selectboxes():
    DEPENDENT_KEYS = ['mark_line_x','mark_line_y','mark_point_x',
                      'mark_point_y','mark_bar_x','mark_bar_y','mark_bar_all']
    for key in DEPENDENT_KEYS:
        st.session_state[key] = None

#Функция преобразования получнного df к корректным типам данных
@st.cache_data()
def smart_parse_df(df):
    error_messages = []  # Список для сбора всех ошибок
    try:
        df = df.copy()
        for col in df.columns:
            try:
                #Очистка данных
                series = df[col].astype(str).str.strip().replace(['nan', 'None', '', 'NaT','null'], np.nan)
                #Преобразуем дату и время
                d_parsed = pd.to_datetime(series, dayfirst=True, format='mixed', errors='coerce')
                #Если удалось распознать дату
                if d_parsed.notna().all():
                    df[col] = d_parsed
                    continue
                #Преобразуем в числа
                n_parsed = pd.to_numeric(series, errors='coerce')
                if n_parsed.notna().any():
                    original_nan_count = series.isna().sum()
                    new_nan_count = n_parsed.isna().sum()
                    # Если новых пропусков меньше чем без преобразования, то тип числа
                    if new_nan_count <= original_nan_count:
                        df[col] = n_parsed
            except Exception as e:
                error_msg = f"Ошибка при обработке колонки '{col}': {str(e)}"
                error_messages.append(error_msg)
                st.warning(error_msg)  
                continue  # Пропускаем проблемную колонку         
        # После обработки всех колонок показываем сводку ошибок, если они были
        if error_messages:
            st.info(f"Обработка завершена с {len(error_messages)} предупреждениями:")
            for msg in error_messages:
                st.write(f"• {msg}")
        else:
            st.success("Все колонки обработаны без ошибок!")       
        return df.convert_dtypes() #преобразуем автоматически оставшиеся типы
    except Exception as e:
        critical_error = f"Критическая ошибка при выполнении функции smart_parse_df: {str(e)}"
        st.error(critical_error)
        # В случае критической ошибки возвращаем копию исходного DataFrame
        return df.copy()

# Функция для форматирования отображения типа данных в столбце при выборе
def format_with_type(column_name, df):
    dtype = str(df[column_name].dtype)
    return f"{column_name} ({dtype})"

#основной блок программы
st.set_page_config(
    page_title="Анализ табличных данных",
    page_icon="😎",
    layout="wide")
st.title("Анализ табличных данных")
 
# Загрузка файла
uploaded_file = st.file_uploader("Загрузите файл с таблицей", type=["csv"], on_change=reset_selection_columns)
if not uploaded_file:
    st.info("Выберите файл для дальнейшей работы с программой")

if uploaded_file:
    # Боковая панель навигации
    option = st.sidebar.radio("Выберите необходимое меню ниже:", 
                            ["Загрузка csv и просмотр данных", "Базовый анализ", "Построение графиков", "Статистические графики"],key="sidebar_radio")
    
    with st.spinner("Загрузка данных..."):
        df = safe_load_table(uploaded_file)
        df_selected_clear = smart_parse_df(df)
        # Выбор столбцов у загруженной таблицы данных
        st.multiselect("Выберите столбцы которы будут использоваться в отчётах:", options=df_selected_clear.columns, key="cols",format_func=lambda x: format_with_type(x, df_selected_clear))
        # Выводим выбранные колонки (если список пуст, то все данные )
        if st.session_state.cols:
            selected = st.session_state.cols
        else:
            selected = df_selected_clear.columns
        df_selected_clear = df_selected_clear[selected]   
        st.divider()         
    #    Выбор боковой панели по умолчанию 
    if option == "Загрузка csv и просмотр данных":
        st.subheader("Таблица полученных данных")
        st.dataframe(df_selected_clear)
        st.subheader("Информация о типах данных в столбцах.")
        # Создаем таблицу с основной информацией о столбцах
        info_df = pd.DataFrame({
            "Наименование столбца": df_selected_clear.columns,
            "Не пустых значений": df_selected_clear.notnull().sum().values,
            "Тип данных столбца": df_selected_clear.dtypes.astype(str).values  
        })
        # Отображаем как интерактивную таблицу
        st.dataframe(info_df)
    #  Следующий пункт боковой панели
    elif option == "Базовый анализ":
        st.subheader("Базовый анализ")
        # Выбираем только числовые колонки
        numeric_df_selected_clear = df_selected_clear.select_dtypes(include=['number'])

        if not numeric_df_selected_clear.empty:
            st.subheader("Статистический анализ")
            #  Статистический анализ для числовых столбцов: вывод среднего, медианы, стандартного отклонения
            col_to_show = st.selectbox("Выберите числовой столбец для получения статистических данных:", numeric_df_selected_clear.columns, index=None)
            if col_to_show is not None:
                mean_value, median_value, std_value = st.columns(3)
                mean_value.metric("Среднее", f"{numeric_df_selected_clear[col_to_show].mean():.2f}")
                median_value.metric("Медиана", f"{numeric_df_selected_clear[col_to_show].median():.2f}")
                std_value.metric("Cтандартное отклонение", f"{numeric_df_selected_clear[col_to_show].std():.2f}")
            else: 
                st.warning("Выберите столбец для анализа.")
        else:
            st.warning("В таблице нет числовых столбцов.")
            
    elif option == "Построение графиков":
        st.subheader("Построение графиков")
        # Подготавливаем список столбцов
        numeric_df_selected_clear = df_selected_clear.select_dtypes(include=['number'])
        num_dat_df_selected_clear = df_selected_clear.select_dtypes(include=['number', 'datetime', 'datetimetz'])
        
        chart_to_show = st.selectbox("Выберите график для построения:", ["Линейный график",
                                                                         "Диаграмма рассеяния",
                                                                         "Cтолбчатая диаграмма"], 
                                     index=None, on_change=reset_char_selectboxes)
        if chart_to_show is not None:
# //////////////////////////////////////////////            
            if chart_to_show == "Линейный график":
                st.subheader('Линейный график.')
                if not num_dat_df_selected_clear.empty:
                    col_to_show_chart_x = st.selectbox(
                        "Выберите числовой столбец или столбец дат для координат X:",
                        options=num_dat_df_selected_clear.columns,
                        index=None,
                        format_func=lambda x: format_with_type(x, num_dat_df_selected_clear),
                        key = 'mark_line_x'
                        )
                else:
                    st.warning("В таблице нет числовых столбцов или столбцов с датами.")
                if not numeric_df_selected_clear.empty:    
                    col_to_show_chart_y = st.selectbox(
                        "Выберите числовой столбец для координат Y:", 
                        numeric_df_selected_clear.columns, 
                        index=None,
                        key = 'mark_line_y'
                        )
                else:
                    st.warning("В таблице нет числовых столбцов.")
                # Проверяем, что пользователь не выбрал одинаковые столбцы
                if (col_to_show_chart_x == col_to_show_chart_y) and (col_to_show_chart_x is not None and col_to_show_chart_y is not None):
                     st.warning("Нельзя выбирать одинаковые столбцы.")
                     col_to_show_chart_x = None
                     col_to_show_chart_y = None
                # Проверяем, что пользователь сделал выбор в обоих полях                     
                if col_to_show_chart_x and col_to_show_chart_y:
                    # Создаем новый DF только с нужными колонками
                    df_for_chart = df_selected_clear[[col_to_show_chart_x, col_to_show_chart_y]]
                    st.write("Данные для графика:")
                    with st.spinner("Построение диаграммы..."):
                    # Преобразуем данные дат к формату ДД.ММ.ГГГГ
                        if pd.api.types.is_datetime64_any_dtype(df_for_chart[col_to_show_chart_x]):
                            x_axis = alt.X(f"{col_to_show_chart_x}:T", 
                                        sort=None, 
                                        title=col_to_show_chart_x,
                                        axis=alt.Axis(format='%d.%m.%Y'))
                        else:
                            x_axis = alt.X(col_to_show_chart_x, 
                                        sort=None, 
                                        title=col_to_show_chart_x)                        
                        # Создание графика Altair
                        chart = alt.Chart(df_for_chart).mark_line().encode(
                            x=x_axis,
                            y=alt.Y(col_to_show_chart_y, title=col_to_show_chart_y),
                        ).properties(title=f"Линейный график по столбцам {col_to_show_chart_x} и {col_to_show_chart_x}"
                                     ).interactive().configure_title(anchor='middle')

                        # Отображаем график
                        st.altair_chart(chart, width='stretch')

                        # Подготавливаем данные для экспорта графика в файл
                        chart_for_export = chart.properties(width=1200, height=600) 
                        png_data = vlc.vegalite_to_png(chart_for_export.to_json(), scale=2)
                        
                    # Кнопка скачивания
                    st.download_button(
                        label="Скачать график",
                        data=png_data,
                        file_name="altair_chart.png",
                        mime="image/png"
                    )
                else:
                    st.info("Пожалуйста, выберите два столбца для отображения данных.")
# ////////////////////////////////////////////////////////
            elif chart_to_show == "Диаграмма рассеяния":
                st.subheader('Диаграмма рассеяния.')
                if not numeric_df_selected_clear.empty:
                    col_to_show_chart_x = st.selectbox(
                        "Выберите числовой столбец для оси координат X:",
                        options=numeric_df_selected_clear.columns,
                        index=None,
                        key = 'mark_point_x'
                        )
                else:
                    st.warning("В таблице нет числовых столбцов.")
                if not numeric_df_selected_clear.empty:    
                    col_to_show_chart_y = st.selectbox(
                        "Выберите числовой столбец для координат Y:", 
                        numeric_df_selected_clear.columns, 
                        index=None,
                        key = 'mark_point_y'
                        )
                else:
                    st.warning("В таблице нет числовых столбцов.")
                # Проверяем, что пользователь не выбрал одинаковые столбцы
                if (col_to_show_chart_x == col_to_show_chart_y) and (col_to_show_chart_x is not None and col_to_show_chart_y is not None):
                     st.warning("Нельзя выбирать одинаковые столбцы.")
                     col_to_show_chart_x = None
                     col_to_show_chart_y = None 
                    # Проверяем, что пользователь сделал выбор в обоих полях               
                if col_to_show_chart_x and col_to_show_chart_y:
                    # Создаем новый DF только с нужными колонками
                    df_for_chart = df_selected_clear[[col_to_show_chart_x, col_to_show_chart_y]]
                    with st.spinner("Построение диаграммы..."):
                        chart = alt.Chart(df_for_chart).mark_point(filled=True, size=60).encode(
                            x=alt.X(col_to_show_chart_x, title=col_to_show_chart_x),
                            y=alt.Y(col_to_show_chart_y, title=col_to_show_chart_y),
                            tooltip=[col_to_show_chart_x, col_to_show_chart_y]
                        ).properties(
                            title = f"Диаграмма рассеяния по столбцам: {col_to_show_chart_x} и {col_to_show_chart_x} ",
                            width='container', 
                            height=400
                        ).interactive().configure_title(anchor='middle')

                        # Отображаем график
                        st.altair_chart(chart, width='stretch')

                        # Подготавливаем данные для экспорта графика в файл
                        chart_for_export = chart.properties(width=1200, height=600) 
                        png_data = vlc.vegalite_to_png(chart_for_export.to_json(), scale=2)

                    # Кнопка скачивания
                    st.download_button(
                        label="Скачать график",
                        data=png_data,
                        file_name="altair_chart.png",
                        mime="image/png"
                    )
                else:
                    st.info("Пожалуйста, выберите два столбца для отображения данных.")
# ////////////////////////////////////////////////////////
            elif chart_to_show == "Cтолбчатая диаграмма":
                st.text('Выбрана Cтолбчатая диаграмма.')
                if not df_selected_clear.empty:
                    col_to_show_chart_x = st.selectbox(
                        "Выберите столбец для оси координат X:",
                        options=df_selected_clear.columns,
                        index=None,
                        key = 'mark_bar_x'
                        )
                if not numeric_df_selected_clear.empty:    
                    col_to_show_chart_y = st.selectbox(
                        "Выберите числовой столбец для координат Y:", 
                        numeric_df_selected_clear.columns, 
                        index=None,
                        key = 'mark_bar_y'
                        )
                else:
                    st.warning("В таблице нет числовых столбцов.")
                # Проверяем, что пользователь не выбрал одинаковые столбцы
                if (col_to_show_chart_x == col_to_show_chart_y) and (col_to_show_chart_x is not None and col_to_show_chart_y is not None):
                     st.warning("Нельзя выбирать одинаковые столбцы.")
                     col_to_show_chart_x = None
                     col_to_show_chart_y = None
                 # Проверяем, что пользователь сделал выбор в обоих полях    
                if col_to_show_chart_x and col_to_show_chart_y:
                    # Создаем новый DF только с нужными колонками
                    df_for_chart = df_selected_clear[[col_to_show_chart_x, col_to_show_chart_y]]
                    

                    with st.spinner("Построение диаграммы..."):
                        # Преобразуем данные дат к формату ДД.ММ.ГГГГ
                        if pd.api.types.is_datetime64_any_dtype(df_for_chart[col_to_show_chart_x]):
                            x_axis = alt.X(f"{col_to_show_chart_x}:T", 
                                        sort=None, 
                                        title=col_to_show_chart_x,
                                        axis=alt.Axis(format='%m.%Y'))
                        else:
                            x_axis = alt.X(col_to_show_chart_x, 
                                        sort=None, 
                                        title=col_to_show_chart_x)
                       
                        chart = alt.Chart(df_for_chart).mark_bar().encode(
                            x=x_axis,
                            y=alt.Y(col_to_show_chart_y, title=col_to_show_chart_y)
                        ).properties(
                            title=f"Столбчатая диаграмма по столбцам: {col_to_show_chart_x} и {col_to_show_chart_y} ", # Заголовок всего графика
                            width='container', 
                            height=400
                        ).configure_title(anchor='middle')

                        # Отображаем график
                        st.altair_chart(chart, width='stretch')

                        # Подготавливаем данные для экспорта графика в файл     
                        chart_for_export = chart.properties(width=1200, height=600) 
                        png_data = vlc.vegalite_to_png(chart_for_export.to_json(), scale=2)

                    # Кнопка скачивания
                    st.download_button(
                        label="Скачать график",
                        data=png_data,
                        file_name="altair_chart.png",
                        mime="image/png"
                    )
                else:
                    st.info("Пожалуйста, выберите два столбца для отображения данных.")   
# //////////////////////////////////////////////            
    elif option == "Статистические графики":
        st.subheader('Статистические графики.')
        numeric_df_selected_clear = df_selected_clear.select_dtypes(include=['number'])       
        if not numeric_df_selected_clear.empty:    
            selected_column = st.selectbox(
                "Выберите числовой столбец для анализа распределения", 
                numeric_df_selected_clear.columns, 
                index=0,
                key = 'mark_bar_all'
                )
            if selected_column:
                # Выбор типа графика
                chart_type = st.radio(
                    "Тип графика",
                    ["Гистограмма", "Кривая плотности"]
                )

                if chart_type == "Гистограмма":
                    chart = alt.Chart(numeric_df_selected_clear).mark_bar(opacity=0.7).encode(
                        alt.X(f"{selected_column}:Q", bin=alt.Bin(maxbins=30), title=selected_column),
                        alt.Y('count()', title="Частота"),
                        tooltip=[f"{selected_column}", 'count()']
                    ).properties(
                        title=f"Гистограмма распределения: {selected_column}",
                        width=600,
                        height=400
                    )                   
                else:  # Кривая плотности
                    chart = alt.Chart(numeric_df_selected_clear).transform_density(
                        selected_column,
                        as_=[selected_column, 'density'],
                        bandwidth=0.5
                    ).mark_area(opacity=0.6).encode(
                        x=alt.X(f'{selected_column}:Q', title=selected_column),
                        y=alt.Y('density:Q', title="Плотность")
                    ).properties(
                        title=f"Кривая плотности распределения: {selected_column}",
                        width=600,
                        height=400
                    )
                st.altair_chart(chart, width='stretch')           
        else:
            st.warning("В таблице нет числовых столбцов.")     
        st.divider()
            
            
            
            


                    
                    
                                    

