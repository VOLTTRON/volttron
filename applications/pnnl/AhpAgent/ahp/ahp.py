import math
import operator
import sys


# Function to diplay the critieria matrix
def display_matrix(m, labelstring, xlabels, ylabels, rowstring, display_func=sys.stdout):
    # Display header
    print >> display_func, labelstring % tuple(xlabels)

    i = 0
    while i < len(ylabels):
        print >> display_func, rowstring % ((ylabels[i],) + tuple(m[i]))
        i += 1


# Calculates the column sum vector for a given matrix m
def calc_column_sums(m):
    j = 0
    csum = []

    while j < len(m[0]):
        col = [float(row[j]) for row in m]

        # print "col", col, sum(col), t1sum
        csum.append(sum(col))
        j += 1
    return csum


# Normalizes the members of matrix m using the vector col_sums
# Returns the normalized matrix, and the sums of each row of the matrix
def normalize_matrix(m, col_sums):
    normalized_matrix = []
    rowsums = []

    i = 0
    while i < len(m):
        j = 0
        norm_row = []
        while j < len(m[0]):
            norm_row.append(m[i][j]/(col_sums[j] if col_sums[j] != 0 else 1))
            j += 1
        rowsum = sum(norm_row)
        # norm_row.append(rowsum/j)
        rowsums.append(rowsum/j)
        normalized_matrix.append(norm_row)
        i += 1

    return normalized_matrix, rowsums


# Calculates the curtailment score using the normalized matrix m, and the weights vector
# Returns a sorted vector of weights for each device that is a candidate for curtailment
def build_score(m, weight, labels):
    score_matrix = []
    for i in range(0, len(m)):
        criteria_sum = 0
        for j in range(0, len(weight)):
            criteria_sum += m[i][j] * weight[j]
        score_matrix.append([labels[i], criteria_sum])
    return sorted(score_matrix, key=lambda l: l[1], reverse=True)


# TODO: Remove when demo is over
def demo_ahp(criteria_matrix, device_matrix, devices, criteria_labels="", criteria_labelstring="", matrix_rowstring="", display_dest=sys.stdout):
    print >> display_dest, "Criteria Matrix"
    display_matrix(criteria_matrix, criteria_labelstring, criteria_labels, criteria_labels, matrix_rowstring, display_dest)
    # Calculate the column sums for use in validating and normalizing the input matrix
    col_sums = calc_column_sums(criteria_matrix)

    print >> display_dest, ""

    # Validate the criteria matrix
    # print >> display_dest, "================ Validating Criteria Input ================"
    # if(not validate_input(criteria_matrix, col_sums, True, criteria_labels, criteria_labelstring, matrix_rowstring)):
    #     sys.exit(1)

    print >> display_dest, "================ Calculating Curtailment Candidates ================"
    # Normalize the matrix and retrieve the row averages
    (normalized_matrix, row_average) = normalize_matrix(criteria_matrix, col_sums)
    # display_matrix(normalized_matrix, criteria_labelstring+'%9s', criteria_labels+['Average', ], matrix_rowstring+'%9.3f')
    print >> display_dest, "Normalized matrix"
    display_matrix(normalized_matrix, criteria_labelstring, criteria_labels, criteria_labels, matrix_rowstring, display_dest)

    # Calculate the column sums for the matrix of devices that are candidates for curtailment
    print >> display_dest, "Calculating column sums"
    # display_matrix(device_matrix, criteria_labelstring, criteria_labels, devices, matrix_rowstring)
    device_csums = calc_column_sums(device_matrix)
    print >> display_dest, device_csums
    (device_normalized_matrix, dummy) = normalize_matrix(device_matrix, device_csums)

    print >> display_dest, "\nDevice Matrix"
    display_matrix(device_matrix, criteria_labelstring, criteria_labels, devices, matrix_rowstring, display_dest)
    display_matrix([device_csums, ], criteria_labelstring, criteria_labels, ['Device Criteria Sums'], matrix_rowstring, display_dest)
    print >> display_dest, ""
    print >> display_dest, "Normalized device matrix"
    display_matrix(device_normalized_matrix, criteria_labelstring, criteria_labels, devices, matrix_rowstring, display_dest)

    scores = build_score(device_normalized_matrix, row_average, devices)
    print >> display_dest, ""
    print >> display_dest, scores
    return scores


def do_ahp(criteria_matrix, device_matrix, devices):
    # Calculate the column sums for use in validating and normalizing the input matrix
    col_sums = calc_column_sums(criteria_matrix)

    # Validate the criteria matrix
    if(not validate_input(criteria_matrix, col_sums, False)):
        sys.exit(1)

    # Normalize the matrix and retrieve the row averages
    (normalized_matrix, row_average) = normalize_matrix(criteria_matrix, col_sums)
    # display_matrix(normalized_matrix, criteria_labelstring+'%9s', criteria_labels+['Average', ], matrix_rowstring+'%9.3f')

    # Calculate the column sums for the matrix of devices that are candidates for curtailment
    device_csums = calc_column_sums(device_matrix)
    (device_normalized_matrix, dummy) = normalize_matrix(device_matrix, device_csums)

    scores = build_score(device_normalized_matrix, row_average, devices)
    return scores


# Validates the criteria matrix to ensure that the inputs are internally consistent
# Returns a True if the matrix is valid, and False if it is not.
def validate_input(pairwise_matrix, col_sums, display=False, criteria_labels="", criteria_labelstring="", matrix_rowstring="", display_dest=sys.stdout):
    # Calculate row products and take the 5th root
    print >> display_dest, "Validating matrix"
    random_index = [0, 0, 0, 0.58, 0.9, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49]
    roots = []
    for row in pairwise_matrix:
        roots.append(math.pow(reduce(operator.mul, row, 1), 1.0/5))

    display_matrix([roots, ], criteria_labelstring, criteria_labels, ['5th root of product'], matrix_rowstring, display_dest) if display else ""

    # Sum the vector of products
    root_sum = sum(roots)

    # Calculate the priority vector
    priority_vec = []
    for item in roots:
        priority_vec.append(item / root_sum)

    display_matrix([priority_vec, ], criteria_labelstring, criteria_labels, ['Priority Vector'], matrix_rowstring, display_dest) if display else ""

    # Calculate the priorty row
    priority_row = []
    for i in range(0, len(col_sums)):
        priority_row.append(col_sums[i] * priority_vec[i])

    display_matrix([priority_row, ], criteria_labelstring, criteria_labels, ['Priority Row'], matrix_rowstring, display_dest) if display else ""

    # Sum the priority row
    priority_row_sum = sum(priority_row)

    if display:
        print >> display_dest, "Priority row sum: ", priority_row_sum

    # Calculate the consistency index
    consistency_index = (priority_row_sum - len(col_sums)) / (len(col_sums) - 1)

    if display:
        print >> display_dest, "Consistency Index:", consistency_index

    # Calculate the consistency ratio
    consistency_ratio = consistency_index / random_index[len(col_sums)]

    if display:
        print >> display_dest, "Consistency Ratio:", consistency_ratio
    return consistency_ratio < 0.2
