from flask import Flask, render_template
from flask_wtf import FlaskForm
from wtforms import FloatField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from math import pi, sin, radians

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'


class PermeabilityCalculator(FlaskForm):
    # Core properties
    radius = FloatField('Core cross-sectional radius (cm)',
                        validators=[DataRequired(), NumberRange(min=0)])
    length = FloatField('Core length (cm)',
                        validators=[DataRequired(), NumberRange(min=0)])
    angle = FloatField('Core inclination (degrees)',
                       validators=[DataRequired(),
                                   NumberRange(min=-90, max=90)])
    # Fluid properties
    flowrate = FloatField('Fluid flow rate (cm^3/s)',
                          validators=[DataRequired(), NumberRange(min=0)])
    density = FloatField('Fluid density (kg/m^3)',
                         validators=[NumberRange(min=0)],
                         default=1000)  # Default value for water
    viscosity = FloatField('Fluid viscosity (Pa.s)',
                           validators=[NumberRange(min=0)],
                           default=0.001)  # Default value for water
    inlet_pressure = FloatField('Fluid inlet pressure (Pa)',
                                validators=[DataRequired(),
                                            NumberRange(min=0)])
    outlet_pressure = FloatField('Fluid outlet pressure (Pa)',
                                 validators=[DataRequired(),
                                             NumberRange(min=0)])
    # Submit button
    submit = SubmitField('Calculate')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/permeability', methods=['GET', 'POST'])
def calculate_permeability():
    calculator = PermeabilityCalculator()
    permeability = None
    if calculator.validate_on_submit():
        radius = calculator.radius.data / 100  # Convert to m
        length = calculator.length.data / 100  # Convert to m
        angle = radians(calculator.angle.data)  # Convert to radians
        flowrate = calculator.flowrate.data / 10**6  # Convert to m^3/s
        density = calculator.density.data
        viscosity = calculator.viscosity.data
        inlet_pressure = calculator.inlet_pressure.data
        outlet_pressure = calculator.outlet_pressure.data
        # Calculate permeability
        darcy_velocity = flowrate / (pi * radius**2)
        gravity = 9.81 * sin(angle)
        pressure_gradient = (inlet_pressure - outlet_pressure) / length
        permeability = (darcy_velocity * viscosity) / \
            (pressure_gradient + (density * gravity)) * 10**12  # in Darcy
    return render_template('permeability.html',
                           form=calculator,
                           permeability=permeability)


if __name__ == '__main__':
    app.run(debug=True)  # Add debug=True to run the app in debug mode
